"""
Manus Visualizer Service
Nhận mảng JSON data, sinh ra cấu hình Echarts/Recharts JSON
để Frontend component DynamicChart tự động render thành biểu đồ.
"""

import json
import logging
from typing import Any, Dict, List

from backend.services.llm_client import chat_completion, is_configured

logger = logging.getLogger(__name__)

CHART_SYSTEM_PROMPT = """You are a data visualization expert. Given a JSON dataset and a user question,
generate an appropriate chart configuration in JSON format compatible with Recharts/Echarts.

Rules:
1. Analyze the data structure and choose the best chart type (bar, line, pie, area, scatter, composed)
2. Return a JSON object with the following structure:
{
    "chart_type": "bar|line|pie|area|scatter|composed",
    "title": "Chart title in English",
    "description": "Brief description of what the chart shows",
    "config": {
        "xAxis": {"dataKey": "field_name", "label": "Label"},
        "yAxis": {"label": "Label"},
        "series": [
            {"dataKey": "field_name", "name": "Series name", "color": "#hex_color"}
        ]
    },
    "data": [...processed data array...]
}
3. For pie charts, use: {"nameKey": "field", "dataKey": "value", "data": [...]}
4. Always use English for labels and titles
5. Choose visually appealing colors
6. Return ONLY valid JSON, no markdown or explanation
"""


async def generate_chart_config(
    data: List[Dict[str, Any]],
    user_question: str,
) -> Dict[str, Any]:
    """
    Sinh cấu hình biểu đồ từ dữ liệu JSON.
    """
    if not data:
        return {
            "chart_type": "empty",
            "title": "No data available",
            "description": "The query returned no rows.",
            "config": {},
            "data": [],
        }

    if not is_configured():
        logger.warning("LLM not configured, using fallback chart config")
        return _fallback_chart_config(data, user_question)

    try:
        sample_data = data[:50] if len(data) > 50 else data

        serialized_data = json.dumps(
            sample_data,
            default=str,
            ensure_ascii=False,
            indent=2
        )

        user_message = f"""User question: {user_question}

Data (JSON array):
{serialized_data}

Total rows: {len(data)}

Generate the best chart configuration for this data."""

        content = await chat_completion(
            messages=[
                {"role": "system", "content": CHART_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        chart_config = json.loads(content)
        logger.info(f"Generated chart config: type={chart_config.get('chart_type')}")
        return chart_config

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse chart config JSON: {e}")
        return _fallback_chart_config(data, user_question)
    except Exception as e:
        logger.error(f"Error generating chart config: {e}")
        return _fallback_chart_config(data, user_question)


def _fallback_chart_config(
    data: List[Dict[str, Any]],
    user_question: str
) -> Dict[str, Any]:
    """
    Fallback: Tự sinh cấu hình biểu đồ cơ bản khi LLM không khả dụng.
    """
    if not data:
        return {"chart_type": "empty", "title": "No data available", "config": {}, "data": []}

    keys = list(data[0].keys())

    numeric_keys = []
    text_keys = []
    for key in keys:
        sample_val = data[0][key]
        if isinstance(sample_val, (int, float)):
            numeric_keys.append(key)
        else:
            text_keys.append(key)

    if not numeric_keys:
        return {
            "chart_type": "table",
            "title": "Query results",
            "description": "Tabular dataset",
            "config": {"columns": keys},
            "data": data[:100],
        }

    x_key = text_keys[0] if text_keys else keys[0]

    colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]

    series = []
    for i, nk in enumerate(numeric_keys[:3]):
        series.append({
            "dataKey": nk,
            "name": nk.replace("_", " ").title(),
            "color": colors[i % len(colors)],
        })

    return {
        "chart_type": "bar",
        "title": "Data analysis chart",
        "description": f"Breakdown by {x_key}",
        "config": {
            "xAxis": {"dataKey": x_key, "label": x_key.replace("_", " ").title()},
            "yAxis": {"label": numeric_keys[0].replace("_", " ").title()},
            "series": series,
        },
        "data": data[:100],
    }


async def generate_insight_summary(
    data: List[Dict[str, Any]],
    user_question: str,
) -> str:
    """
    Sinh tóm tắt insight từ dữ liệu.
    """
    if not is_configured():
        return "Unable to generate AI insight because no LLM is configured. Please review the chart data directly."

    try:
        serialized = json.dumps(data[:30], default=str, ensure_ascii=False)

        content = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are a business data analyst. Summarize key insights in English. Be concise, actionable, and factual in 3-4 sentences."
                },
                {
                    "role": "user",
                    "content": f"Question: {user_question}\n\nData:\n{serialized}"
                },
            ],
            temperature=0.5,
            max_tokens=500,
        )

        return content
    except Exception as e:
        logger.error(f"Error generating insight: {e}")
        return "Unable to generate AI insight at the moment. Please review the chart data directly."
