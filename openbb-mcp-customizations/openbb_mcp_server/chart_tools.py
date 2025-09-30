"""Free charting tools.

Provides chart generation using free providers:
- QuickChart (serverless chart rendering)
"""

import logging
import urllib.parse
from typing import Dict, List, Any, Optional
from datetime import datetime

from shared.http_client import BaseHTTPTool, ProviderError

logger = logging.getLogger(__name__)


class QuickChartGenerator:
    """Generate charts using QuickChart API."""

    def __init__(self):
        self.client = BaseHTTPTool(
            provider_name="quickchart",
            base_url="https://quickchart.io",
            timeout=30.0,
            cache_ttl=300  # 5-minute cache
        )

    async def generate_line_chart(
        self,
        labels: List[str],
        datasets: List[Dict[str, Any]],
        title: Optional[str] = None,
        width: int = 500,
        height: int = 300
    ) -> Dict[str, Any]:
        """
        Generate a line chart.

        Args:
            labels: X-axis labels (dates, categories, etc.)
            datasets: List of dataset dicts with 'label', 'data', and optional 'borderColor'
            title: Chart title
            width: Chart width in pixels (default 500)
            height: Chart height in pixels (default 300)

        Returns:
            Dict with chart URL and metadata
        """
        try:
            # Build Chart.js configuration
            chart_config = {
                "type": "line",
                "data": {
                    "labels": labels,
                    "datasets": []
                },
                "options": {
                    "responsive": True,
                    "plugins": {
                        "legend": {
                            "display": True,
                            "position": "top"
                        }
                    },
                    "scales": {
                        "y": {
                            "beginAtZero": False
                        }
                    }
                }
            }

            # Add title if provided
            if title:
                chart_config["options"]["plugins"]["title"] = {
                    "display": True,
                    "text": title
                }

            # Add datasets with default colors
            default_colors = [
                "rgb(75, 192, 192)",  # teal
                "rgb(255, 99, 132)",  # red
                "rgb(54, 162, 235)",  # blue
                "rgb(255, 206, 86)",  # yellow
                "rgb(153, 102, 255)"  # purple
            ]

            for i, dataset in enumerate(datasets):
                color = dataset.get("borderColor", default_colors[i % len(default_colors)])
                chart_config["data"]["datasets"].append({
                    "label": dataset.get("label", f"Series {i + 1}"),
                    "data": dataset.get("data", []),
                    "borderColor": color,
                    "backgroundColor": color.replace("rgb", "rgba").replace(")", ", 0.1)"),
                    "fill": False,
                    "tension": 0.1
                })

            # Generate chart URL
            import json
            chart_json = json.dumps(chart_config)
            chart_url = f"https://quickchart.io/chart?c={urllib.parse.quote(chart_json)}&width={width}&height={height}"

            return {
                "chart_url": chart_url,
                "chart_type": "line",
                "width": width,
                "height": height,
                "title": title,
                "datasets_count": len(datasets),
                "source": "quickchart",
                "provider": "quickchart"
            }

        except Exception as e:
            logger.error(f"QuickChart line chart generation failed: {e}")
            raise ProviderError(f"QuickChart error: {e}")

    async def generate_bar_chart(
        self,
        labels: List[str],
        datasets: List[Dict[str, Any]],
        title: Optional[str] = None,
        width: int = 500,
        height: int = 300
    ) -> Dict[str, Any]:
        """
        Generate a bar chart.

        Args:
            labels: X-axis labels
            datasets: List of dataset dicts with 'label' and 'data'
            title: Chart title
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Dict with chart URL and metadata
        """
        try:
            # Build Chart.js configuration
            chart_config = {
                "type": "bar",
                "data": {
                    "labels": labels,
                    "datasets": []
                },
                "options": {
                    "responsive": True,
                    "plugins": {
                        "legend": {
                            "display": True,
                            "position": "top"
                        }
                    }
                }
            }

            # Add title if provided
            if title:
                chart_config["options"]["plugins"]["title"] = {
                    "display": True,
                    "text": title
                }

            # Add datasets with default colors
            default_colors = [
                "rgba(75, 192, 192, 0.8)",
                "rgba(255, 99, 132, 0.8)",
                "rgba(54, 162, 235, 0.8)",
                "rgba(255, 206, 86, 0.8)",
                "rgba(153, 102, 255, 0.8)"
            ]

            for i, dataset in enumerate(datasets):
                color = dataset.get("backgroundColor", default_colors[i % len(default_colors)])
                chart_config["data"]["datasets"].append({
                    "label": dataset.get("label", f"Series {i + 1}"),
                    "data": dataset.get("data", []),
                    "backgroundColor": color
                })

            # Generate chart URL
            import json
            chart_json = json.dumps(chart_config)
            chart_url = f"https://quickchart.io/chart?c={urllib.parse.quote(chart_json)}&width={width}&height={height}"

            return {
                "chart_url": chart_url,
                "chart_type": "bar",
                "width": width,
                "height": height,
                "title": title,
                "datasets_count": len(datasets),
                "source": "quickchart",
                "provider": "quickchart"
            }

        except Exception as e:
            logger.error(f"QuickChart bar chart generation failed: {e}")
            raise ProviderError(f"QuickChart error: {e}")


# Module-level singleton to prevent socket leaks
_quickchart_generator = QuickChartGenerator()


# MCP tool wrappers
async def mcp_chart_line(
    labels: List[str],
    datasets: List[Dict[str, Any]],
    title: Optional[str] = None,
    width: int = 500,
    height: int = 300
) -> Dict[str, Any]:
    """
    MCP wrapper for line chart generation.

    Args:
        labels: X-axis labels (e.g., dates, time periods)
        datasets: List of datasets, each with:
            - label: Series name
            - data: List of numeric values
            - borderColor: Optional color (e.g., 'rgb(75, 192, 192)')
        title: Optional chart title
        width: Chart width in pixels (default 500)
        height: Chart height in pixels (default 300)

    Returns:
        Dict containing:
            - chart_url: URL to the generated chart image
            - chart_type: Type of chart ('line')
            - metadata

    Example:
        mcp_chart_line(
            labels=["2024-01", "2024-02", "2024-03"],
            datasets=[
                {"label": "Revenue", "data": [100, 120, 135]},
                {"label": "Expenses", "data": [80, 85, 90]}
            ],
            title="Revenue vs Expenses"
        )
    """
    try:
        # Use module-level singleton to avoid socket leaks
        result = await _quickchart_generator.generate_line_chart(
            labels=labels,
            datasets=datasets,
            title=title,
            width=width,
            height=height
        )

        return result

    except Exception as e:
        logger.error(f"Error generating line chart: {e}")
        return {
            "error": str(e),
            "chart_type": "line"
        }


async def mcp_chart_bar(
    labels: List[str],
    datasets: List[Dict[str, Any]],
    title: Optional[str] = None,
    width: int = 500,
    height: int = 300
) -> Dict[str, Any]:
    """
    MCP wrapper for bar chart generation.

    Args:
        labels: X-axis labels (e.g., categories, months)
        datasets: List of datasets, each with:
            - label: Series name
            - data: List of numeric values
            - backgroundColor: Optional color
        title: Optional chart title
        width: Chart width in pixels (default 500)
        height: Chart height in pixels (default 300)

    Returns:
        Dict containing chart URL and metadata

    Example:
        mcp_chart_bar(
            labels=["Q1", "Q2", "Q3", "Q4"],
            datasets=[{"label": "Sales", "data": [120, 150, 180, 200]}],
            title="Quarterly Sales"
        )
    """
    try:
        # Use module-level singleton to avoid socket leaks
        result = await _quickchart_generator.generate_bar_chart(
            labels=labels,
            datasets=datasets,
            title=title,
            width=width,
            height=height
        )

        return result

    except Exception as e:
        logger.error(f"Error generating bar chart: {e}")
        return {
            "error": str(e),
            "chart_type": "bar"
        }