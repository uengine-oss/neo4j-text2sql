from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Pattern, Tuple

from app.react.utils import XmlUtil


@dataclass
class _FieldState:
    """
    Tracks incremental extraction for one XML field like <reasoning>...</reasoning>.
    """

    name: str
    start_re: Pattern[str]
    end_re: Pattern[str]
    next_re: List[Pattern[str]]
    content_start: Optional[int] = None
    last_emitted_len: int = 0


def _unwrap_cdata_best_effort(text: str) -> str:
    # Best effort: strip CDATA wrapper when present, even if it's partial.
    if not text:
        return text
    if text.startswith("<![CDATA["):
        text = text[len("<![CDATA[") :]
    # Remove first occurrence of the CDATA end marker if present.
    end_idx = text.find("]]>")
    if end_idx >= 0:
        text = text[:end_idx] + text[end_idx + len("]]>") :]
    return text


_INCOMPLETE_TAG_TAIL_RE = re.compile(r"<\s*/?\s*[A-Za-z_][A-Za-z0-9_.:-]*\s*$")


def _trim_trailing_incomplete_tag(text: str) -> str:
    """
    If the tail looks like an incomplete XML tag fragment (no closing '>'),
    trim it to avoid leaking '<collected_met...' artifacts into streaming UI.
    """
    if not text or "<" not in text:
        return text
    lt = text.rfind("<")
    if lt < 0:
        return text
    tail = text[lt:]
    if ">" in tail:
        return text
    if _INCOMPLETE_TAG_TAIL_RE.match(tail):
        return text[:lt]
    return text


def _normalize_visible_text(raw: str) -> str:
    out = raw or ""
    out = _unwrap_cdata_best_effort(out)
    out = _trim_trailing_incomplete_tag(out)
    return out


class StreamingXmlSectionsExtractor:
    """
    Incrementally extracts user-facing sections from a streaming XML output.

    It is intentionally best-effort and does NOT require well-formed XML at all times.
    It supports:
    - section deltas for: reasoning, partial_sql, sql_completeness_check fields, tool_call fields
    - collected_metadata item streaming: table/column/value/relationship/constraint blocks
    - 50ms flush throttling (batching)
    """

    def __init__(self, *, throttle_ms: int = 50):
        self._throttle_s = max(float(throttle_ms) / 1000.0, 0.0)
        self._last_flush = time.monotonic()
        self._iteration: Optional[int] = None
        self._buf: str = ""

        # Pending (batched) outgoing events.
        self._pending_section_delta: Dict[str, str] = {}
        self._pending_metadata_items: List[Dict[str, Any]] = []

        # Fields to stream as text deltas (grouped by UI sections later).
        # We stream fine-grained field keys so UI can render each sub-field cleanly.
        self._fields: List[_FieldState] = [
            _FieldState(
                name="reasoning",
                start_re=re.compile(r"<reasoning\b[^>]*>", re.IGNORECASE),
                end_re=re.compile(r"</reasoning\s*>", re.IGNORECASE),
                next_re=[
                    re.compile(r"<collected_metadata\b", re.IGNORECASE),
                    re.compile(r"<partial_sql\b", re.IGNORECASE),
                    re.compile(r"<sql_completeness_check\b", re.IGNORECASE),
                    re.compile(r"<tool_call\b", re.IGNORECASE),
                    re.compile(r"</output\s*>", re.IGNORECASE),
                ],
            ),
            _FieldState(
                name="partial_sql",
                start_re=re.compile(r"<partial_sql\b[^>]*>", re.IGNORECASE),
                end_re=re.compile(r"</partial_sql\s*>", re.IGNORECASE),
                next_re=[
                    re.compile(r"<sql_completeness_check\b", re.IGNORECASE),
                    re.compile(r"<tool_call\b", re.IGNORECASE),
                    re.compile(r"</output\s*>", re.IGNORECASE),
                ],
            ),
            _FieldState(
                name="sql_completeness_check.is_complete",
                start_re=re.compile(r"<is_complete\b[^>]*>", re.IGNORECASE),
                end_re=re.compile(r"</is_complete\s*>", re.IGNORECASE),
                next_re=[
                    re.compile(r"<missing_info\b", re.IGNORECASE),
                    re.compile(r"<confidence_level\b", re.IGNORECASE),
                    re.compile(r"</sql_completeness_check\s*>", re.IGNORECASE),
                ],
            ),
            _FieldState(
                name="sql_completeness_check.missing_info",
                start_re=re.compile(r"<missing_info\b[^>]*>", re.IGNORECASE),
                end_re=re.compile(r"</missing_info\s*>", re.IGNORECASE),
                next_re=[
                    re.compile(r"<confidence_level\b", re.IGNORECASE),
                    re.compile(r"</sql_completeness_check\s*>", re.IGNORECASE),
                ],
            ),
            _FieldState(
                name="sql_completeness_check.confidence_level",
                start_re=re.compile(r"<confidence_level\b[^>]*>", re.IGNORECASE),
                end_re=re.compile(r"</confidence_level\s*>", re.IGNORECASE),
                next_re=[
                    re.compile(r"</sql_completeness_check\s*>", re.IGNORECASE),
                ],
            ),
            _FieldState(
                name="tool_call.tool_name",
                start_re=re.compile(r"<tool_name\b[^>]*>", re.IGNORECASE),
                end_re=re.compile(r"</tool_name\s*>", re.IGNORECASE),
                next_re=[
                    re.compile(r"<parameters\b", re.IGNORECASE),
                    re.compile(r"</tool_call\s*>", re.IGNORECASE),
                ],
            ),
            _FieldState(
                name="tool_call.parameters",
                start_re=re.compile(r"<parameters\b[^>]*>", re.IGNORECASE),
                end_re=re.compile(r"</parameters\s*>", re.IGNORECASE),
                next_re=[
                    re.compile(r"</tool_call\s*>", re.IGNORECASE),
                ],
            ),
        ]

        # collected_metadata: item streaming state
        self._collected_meta_start_re = re.compile(r"<collected_metadata\b[^>]*>", re.IGNORECASE)
        self._collected_meta_end_re = re.compile(r"</collected_metadata\s*>", re.IGNORECASE)
        self._collected_meta_next_re = [
            re.compile(r"<partial_sql\b", re.IGNORECASE),
            re.compile(r"<sql_completeness_check\b", re.IGNORECASE),
            re.compile(r"<tool_call\b", re.IGNORECASE),
            re.compile(r"</output\s*>", re.IGNORECASE),
        ]
        self._meta_content_start: Optional[int] = None
        self._meta_scan_pos: int = 0  # relative to meta content start

        # Item block finders
        self._meta_item_open_res: List[Tuple[str, Pattern[str]]] = [
            ("table", re.compile(r"<table\b[^>]*>", re.IGNORECASE)),
            ("column", re.compile(r"<column\b[^>]*>", re.IGNORECASE)),
            ("value", re.compile(r"<value\b[^>]*>", re.IGNORECASE)),
            ("relationship", re.compile(r"<relationship\b[^>]*>", re.IGNORECASE)),
            ("constraint", re.compile(r"<constraint\b[^>]*>", re.IGNORECASE)),
        ]

    def reset_iteration(self, iteration: int) -> None:
        self._iteration = iteration
        self._buf = ""
        self._pending_section_delta.clear()
        self._pending_metadata_items.clear()
        for f in self._fields:
            f.content_start = None
            f.last_emitted_len = 0
        self._meta_content_start = None
        self._meta_scan_pos = 0

    def feed(self, *, iteration: int, token: str) -> None:
        if self._iteration is None or self._iteration != iteration:
            self.reset_iteration(iteration)
        self._buf += token or ""
        self._update_fields()
        self._update_metadata_items()

    def flush_if_due(self, *, force: bool = False) -> List[Dict[str, Any]]:
        now = time.monotonic()
        if not force and (now - self._last_flush) < self._throttle_s:
            return []
        self._last_flush = now

        out: List[Dict[str, Any]] = []
        if self._iteration is None:
            return out

        for section, delta in list(self._pending_section_delta.items()):
            if not delta:
                continue
            out.append(
                {
                    "event": "section_delta",
                    "iteration": self._iteration,
                    "section": section,
                    "delta": delta,
                }
            )
        self._pending_section_delta.clear()

        out.extend(self._pending_metadata_items)
        self._pending_metadata_items = []
        return out

    def _update_fields(self) -> None:
        buf = self._buf
        for f in self._fields:
            if f.content_start is None:
                m = f.start_re.search(buf)
                if not m:
                    continue
                f.content_start = m.end()
                f.last_emitted_len = 0

            assert f.content_start is not None

            # Determine boundary of visible content.
            end_m = f.end_re.search(buf, f.content_start)
            boundary: Optional[int] = None
            if end_m:
                boundary = end_m.start()
            else:
                # fall back to next-known-tag boundary (to avoid showing subsequent section tags)
                next_positions = []
                for nr in f.next_re:
                    nm = nr.search(buf, f.content_start)
                    if nm:
                        next_positions.append(nm.start())
                if next_positions:
                    boundary = min(next_positions)

            if boundary is None:
                boundary = len(buf)

            visible_raw = buf[f.content_start : boundary]
            visible = _normalize_visible_text(visible_raw)
            if not visible:
                continue

            # Delta-append semantics
            if f.last_emitted_len < len(visible):
                delta = visible[f.last_emitted_len :]
                self._pending_section_delta[f.name] = self._pending_section_delta.get(f.name, "") + delta
                f.last_emitted_len = len(visible)

    def _find_meta_content_range(self) -> Optional[Tuple[int, int]]:
        """
        Return (content_start, content_end) indices in self._buf for collected_metadata content.
        If not fully closed yet, content_end is best-effort boundary (next known tag / EOF).
        """
        buf = self._buf
        if self._meta_content_start is None:
            m = self._collected_meta_start_re.search(buf)
            if not m:
                return None
            self._meta_content_start = m.end()
            self._meta_scan_pos = 0

        assert self._meta_content_start is not None

        end_m = self._collected_meta_end_re.search(buf, self._meta_content_start)
        if end_m:
            return (self._meta_content_start, end_m.start())

        next_positions = []
        for nr in self._collected_meta_next_re:
            nm = nr.search(buf, self._meta_content_start)
            if nm:
                next_positions.append(nm.start())
        content_end = min(next_positions) if next_positions else len(buf)
        return (self._meta_content_start, content_end)

    def _update_metadata_items(self) -> None:
        rng = self._find_meta_content_range()
        if not rng:
            return
        start, end = rng
        if end <= start:
            return

        meta_text = self._buf[start:end]
        scan = min(max(self._meta_scan_pos, 0), len(meta_text))

        while True:
            next_open = self._find_next_meta_open(meta_text, scan)
            if not next_open:
                break
            item_type, open_idx, open_end = next_open
            close_tag = f"</{item_type}>"
            close_idx = meta_text.lower().find(close_tag.lower(), open_end)
            if close_idx < 0:
                # Not complete yet
                break
            close_end = close_idx + len(close_tag)
            block = meta_text[open_idx:close_end]
            scan = close_end

            parsed = self._parse_metadata_item(item_type=item_type, xml_block=block)
            if parsed is not None:
                self._pending_metadata_items.append(
                    {
                        "event": "metadata_item",
                        "iteration": self._iteration,
                        "item_type": item_type,
                        "item": parsed,
                    }
                )

        self._meta_scan_pos = scan

    def _find_next_meta_open(self, meta_text: str, start_pos: int) -> Optional[Tuple[str, int, int]]:
        best: Optional[Tuple[str, int, int]] = None
        for item_type, open_re in self._meta_item_open_res:
            m = open_re.search(meta_text, start_pos)
            if not m:
                continue
            cand = (item_type, m.start(), m.end())
            if best is None or cand[1] < best[1]:
                best = cand
        return best

    @staticmethod
    def _parse_metadata_item(*, item_type: str, xml_block: str) -> Optional[Dict[str, Any]]:
        # Repair/sanitize enough for parsing small blocks.
        repaired = XmlUtil.repair_llm_xml_text(
            xml_block,
            text_tag_names=[
                "schema",
                "name",
                "purpose",
                "key_columns",
                "description",
                "table",
                "column",
                "actual_value",
                "user_term",
                "type",
                "condition",
                "tables",
                "status",
                "data_type",
            ],
            repair_parameters_text_only=False,
        )
        sanitized = XmlUtil.sanitize_xml_text(repaired)
        try:
            el = ET.fromstring(sanitized)
        except ET.ParseError:
            return None

        out: Dict[str, Any] = {"_type": item_type}
        # Flatten direct child tags as strings.
        for child in list(el):
            tag = child.tag
            text = "".join(child.itertext()).strip()
            if text:
                out[tag] = text
        return out


