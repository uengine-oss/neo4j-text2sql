import re
from typing import List, Pattern, Tuple


class XmlUtil:
    """XML 관련 유틸리티 함수 모음."""

    _CDATA_PATTERN: Pattern[str] = re.compile(r"<!\[CDATA\[.*?\]\]>", re.DOTALL)
    _AMP_PATTERN: Pattern[str] = re.compile(
        r"&(?!#\d+;|#x[0-9A-Fa-f]+;|[A-Za-z0-9_]+;)"
    )

    # Detect actual element tags like <schema>, </schema>, <tag attr="...">.
    # This intentionally does NOT match "< 3" or "<=" found in SQL.
    _ELEMENT_TAG_START_PATTERN: Pattern[str] = re.compile(r"<\s*/?\s*[A-Za-z_][A-Za-z0-9_.:-]*\b")

    @staticmethod
    def _split_preserving_cdata(xml_text: str) -> List[Tuple[bool, str]]:
        """
        Split text into chunks while preserving CDATA blocks.

        Returns:
            List of (is_cdata, chunk) tuples.
        """
        parts: List[Tuple[bool, str]] = []
        last_idx = 0
        for match in XmlUtil._CDATA_PATTERN.finditer(xml_text):
            if match.start() > last_idx:
                parts.append((False, xml_text[last_idx:match.start()]))
            parts.append((True, match.group(0)))
            last_idx = match.end()
        if last_idx < len(xml_text):
            parts.append((False, xml_text[last_idx:]))
        return parts

    @staticmethod
    def _escape_cdata_end_marker(text: str) -> str:
        """
        Make any embedded ']]>' safe inside CDATA by splitting it.
        """
        if "]]>" not in text:
            return text
        return text.replace("]]>", "]]]]><![CDATA[>")

    @staticmethod
    def _wrap_tag_body_in_cdata(chunk: str, tag_name: str) -> str:
        """
        Wrap a simple <tag>BODY</tag> body in CDATA if BODY contains '<'.

        This is a best-effort repair for LLM outputs that accidentally include
        XML-like markup in free-text fields (e.g., "include a <schema> tag").
        """
        if "<" not in chunk:
            return chunk

        pattern = re.compile(
            rf"<{re.escape(tag_name)}(?P<attrs>\s[^>]*)?>(?P<body>.*?)</{re.escape(tag_name)}>",
            re.DOTALL,
        )

        def repl(m: re.Match[str]) -> str:
            body = m.group("body") or ""
            if "<" not in body:
                return m.group(0)
            # If already CDATA-wrapped (or contains CDATA), don't touch.
            if "<![CDATA[" in body:
                return m.group(0)
            safe_body = XmlUtil._escape_cdata_end_marker(body)
            attrs = m.group("attrs") or ""
            return f"<{tag_name}{attrs}><![CDATA[{safe_body}]]></{tag_name}>"

        return pattern.sub(repl, chunk)

    @staticmethod
    def _wrap_parameters_text_only_in_cdata(chunk: str) -> str:
        """
        Wrap <parameters>TEXT</parameters> in CDATA ONLY when it has no child elements.

        - If it contains child tags like <schema>, <table>, ... we leave it intact.
        - If it contains raw '<' used as an operator (e.g., '2 < 3'), we wrap it.
        """
        if "<parameters" not in chunk or "<" not in chunk:
            return chunk

        pattern = re.compile(r"<parameters(?P<attrs>\s[^>]*)?>(?P<body>.*?)</parameters>", re.DOTALL)

        def repl(m: re.Match[str]) -> str:
            body = m.group("body") or ""
            # Already CDATA; keep as-is
            if "<![CDATA[" in body:
                return m.group(0)
            # If there's no risky '<', no need to wrap.
            if "<" not in body:
                return m.group(0)
            # If body contains actual child element tags, do not wrap (P1).
            if XmlUtil._ELEMENT_TAG_START_PATTERN.search(body):
                return m.group(0)
            safe_body = XmlUtil._escape_cdata_end_marker(body)
            attrs = m.group("attrs") or ""
            return f"<parameters{attrs}><![CDATA[{safe_body}]]></parameters>"

        return pattern.sub(repl, chunk)

    @staticmethod
    def repair_llm_xml_text(
        xml_text: str,
        *,
        text_tag_names: List[str],
        repair_parameters_text_only: bool = True,
    ) -> str:
        """
        Best-effort XML repair for LLM outputs.\n
        - Wrap selected free-text tags in CDATA when they contain '<'\n
        - Wrap <parameters> in CDATA only when it has no child tags (P1)\n
        - Never alters existing CDATA blocks\n
        """
        if not xml_text or "<" not in xml_text:
            return xml_text

        parts = XmlUtil._split_preserving_cdata(xml_text)
        repaired_chunks: List[str] = []
        for is_cdata, chunk in parts:
            if is_cdata:
                repaired_chunks.append(chunk)
                continue

            updated = chunk
            for tag in text_tag_names:
                updated = XmlUtil._wrap_tag_body_in_cdata(updated, tag)
            if repair_parameters_text_only:
                updated = XmlUtil._wrap_parameters_text_only_in_cdata(updated)
            repaired_chunks.append(updated)

        return "".join(repaired_chunks)

    @staticmethod
    def sanitize_xml_text(xml_text: str) -> str:
        """
        Escape bare ampersands outside CDATA sections to avoid XML parsing failures.
        """
        if "&" not in xml_text:
            return xml_text

        sanitized_parts = []
        last_idx = 0

        for match in XmlUtil._CDATA_PATTERN.finditer(xml_text):
            unsafe_chunk = xml_text[last_idx:match.start()]
            sanitized_parts.append(XmlUtil._AMP_PATTERN.sub("&amp;", unsafe_chunk))
            sanitized_parts.append(match.group(0))
            last_idx = match.end()

        tail = xml_text[last_idx:]
        sanitized_parts.append(XmlUtil._AMP_PATTERN.sub("&amp;", tail))

        return "".join(sanitized_parts)

