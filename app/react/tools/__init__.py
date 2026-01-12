from typing import Any, Dict, List
import time
import traceback

from .context import ToolContext
from . import (
    search_tables as search_tables_tool,
    get_table_schema as get_table_schema_tool,
    search_column_values as search_column_values_tool,
    execute_sql_preview as execute_sql_preview_tool,
    explain as explain_tool,
    find_similar_query as find_similar_query_tool,
)
from app.smart_logger import SmartLogger
from app.react.utils.log_sanitize import sanitize_for_log


class ToolExecutionError(Exception):
    """툴 실행 중 발생한 예외를 감싼다."""


TOOL_HANDLERS = {
    "search_tables": search_tables_tool.execute,
    "get_table_schema": get_table_schema_tool.execute,
    "search_column_values": search_column_values_tool.execute,
    "execute_sql_preview": execute_sql_preview_tool.execute,
    "explain": explain_tool.execute,
    "find_similar_query": find_similar_query_tool.execute,
}


async def execute_tool(
    tool_name: str,
    context: ToolContext,
    parameters: Dict[str, Any],
) -> str:
    """
    지정한 툴을 실행하고 XML 문자열 결과를 반환한다.
    parameters 는 툴 별 기대 포맷을 따른다.
    """
    if tool_name not in TOOL_HANDLERS:
        raise ToolExecutionError(f"Unsupported tool: {tool_name}")

    handler = TOOL_HANDLERS[tool_name]

    started = time.perf_counter()
    SmartLogger.log(
        "INFO",
        "react.tool.call",
        category="react.tool.call",
        params=sanitize_for_log(
            {
                "react_run_id": context.react_run_id,
                "tool_name": tool_name,
                "parameters": parameters,
            }
        ),
        # Store raw parameters for reproducibility in detail logs (when file_output enabled)
        max_inline_chars=0,
    )

    try:
        if tool_name == "search_tables":
            keywords: List[str] = parameters.get("keywords", [])
            result = await handler(context, keywords)
        elif tool_name == "get_table_schema":
            table_names: List[str] = parameters.get("table_names", [])
            result = await handler(context, table_names)
        elif tool_name == "search_column_values":
            table_name = parameters.get("table")
            column_name = parameters.get("column")
            schema_name = parameters.get("schema")
            search_keywords: List[str] = parameters.get("search_keywords", [])
            if not table_name or not column_name:
                raise ToolExecutionError("table and column parameters are required")
            result = await handler(
                context,
                table_name,
                column_name,
                search_keywords,
                schema_name,
            )
        elif tool_name == "execute_sql_preview":
            sql_text = parameters.get("sql")
            if not sql_text:
                raise ToolExecutionError("sql parameter is required")
            result = await handler(context, sql_text)
        elif tool_name == "explain":
            sql_text = parameters.get("sql")
            if not sql_text:
                raise ToolExecutionError("sql parameter is required")
            result = await handler(context, sql_text)
        elif tool_name == "find_similar_query":
            question = parameters.get("question")
            min_similarity = parameters.get("min_similarity", 0.3)
            if not question:
                raise ToolExecutionError("question parameter is required")
            result = await handler(context, question, min_similarity)
        else:
            raise ToolExecutionError(f"No handler implemented for tool: {tool_name}")

        SmartLogger.log(
            "INFO",
            "react.tool.result",
            category="react.tool.result",
            params=sanitize_for_log(
                {
                    "react_run_id": context.react_run_id,
                    "tool_name": tool_name,
                    "elapsed_ms": (time.perf_counter() - started) * 1000.0,
                    # Keep raw tool output for reproducibility (saved to detail file when enabled).
                    "tool_result": result,
                }
            ),
            max_inline_chars=0,
        )
        return result
    except Exception as exc:
        SmartLogger.log(
            "ERROR",
            "react.tool.error",
            category="react.tool.error",
            params=sanitize_for_log(
                {
                    "react_run_id": context.react_run_id,
                    "tool_name": tool_name,
                    "elapsed_ms": (time.perf_counter() - started) * 1000.0,
                    "parameters": parameters,
                    "exception": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            ),
            max_inline_chars=0,
        )
        raise

__all__ = [
    "ToolContext",
    "ToolExecutionError",
    "execute_tool",
    "TOOL_HANDLERS",
]

