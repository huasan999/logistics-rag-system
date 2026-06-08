"""
工具注册中心
管理和注册所有可用工具
"""
from typing import Dict, List, Optional, Any
import logging

from src.tools.base_tool import BaseTool, ToolCategory
from src.tools.calculator_tools import LogisticsCalculatorTool, UnitConverterTool
from src.tools.logistics_tools import LogisticsQueryTool, ShippingRateTool, TrackingTool
from src.tools.web_tools import WebSearchTool, WeatherCheckTool


logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册中心"""

    def __init__(self, config=None):
        self.config = config
        self.tools: Dict[str, BaseTool] = {}
        self._initialize_tools()

    def _initialize_tools(self):
        """初始化所有工具"""
        # 计算工具
        self.register_tool(LogisticsCalculatorTool())
        self.register_tool(UnitConverterTool())

        # 物流专业工具
        self.register_tool(LogisticsQueryTool())
        self.register_tool(ShippingRateTool())
        self.register_tool(TrackingTool())

        # 网络工具
        self.register_tool(WebSearchTool())
        self.register_tool(WeatherCheckTool())

        logger.info(f"工具注册完成，共 {len(self.tools)} 个工具")

    def register_tool(self, tool: BaseTool):
        """注册工具"""
        self.tools[tool.schema.name] = tool
        logger.debug(f"注册工具: {tool.schema.name}")

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self.tools.get(tool_name)

    def get_all_tools(self) -> List[BaseTool]:
        """获取所有工具"""
        return list(self.tools.values())

    def get_tools_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """按分类获取工具"""
        return [tool for tool in self.tools.values() if tool.schema.category == category]

    def get_function_call_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的Function Call模式"""
        return [tool.to_function_call_format() for tool in self.tools.values()]

    async def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        tool = self.get_tool(tool_name)
        if not tool:
            return {"error": f"工具 '{tool_name}' 未找到"}

        try:
            logger.info(f"执行工具: {tool_name}")
            result = await tool.execute(**kwargs)
            return result
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return {"error": f"工具执行失败: {str(e)}"}

    def match_tool_by_query(self, query: str) -> Optional[str]:
        """根据查询匹配工具"""
        query_lower = query.lower()

        # 关键词到工具的映射
        keyword_mapping = {
            "calculate": "logistics_calculator",
            "compute": "logistics_calculator",
            "cost": "logistics_calculator",
            "price": "logistics_calculator",
            "time": "logistics_calculator",
            "eoq": "logistics_calculator",

            "convert": "unit_converter",
            "unit": "unit_converter",
            "kg": "unit_converter",
            "lb": "unit_converter",

            "query": "logistics_query",
            "what is": "logistics_query",
            "define": "logistics_query",
            "explain": "logistics_query",

            "shipping": "shipping_rate_query",
            "rate": "shipping_rate_query",
            "quote": "shipping_rate_query",
            "freight": "shipping_rate_query",

            "track": "logistics_tracking",
            "tracking": "logistics_tracking",
            "status": "logistics_tracking",

            "search": "web_search",
            "latest": "web_search",
            "news": "web_search",

            "weather": "weather_check",
            "forecast": "weather_check",
            "rain": "weather_check"
        }

        for keyword, tool_name in keyword_mapping.items():
            if keyword in query_lower and tool_name in self.tools:
                return tool_name

        return None


# 全局工具注册实例
_tool_registry = None

def get_tool_registry(config=None) -> ToolRegistry:
    """获取全局工具注册实例"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry(config)
    return _tool_registry