"""
网络工具类
提供网络请求和外部API调用功能

"""
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta

from src.tools.base_tool import BaseTool, ToolSchema, ToolParameter, ToolCategory


class WebSearchTool(BaseTool):
    """网络搜索工具"""

    def get_schema(self) -> ToolSchema:
        """
        获取工具的元数据定义

        Returns:
            ToolSchema: 工具的结构化描述，包括名称、描述、分类、参数和返回值格式
        """
        return ToolSchema(
            name="web_search",
            description="搜索互联网上的物流信息、新闻、价格等",
            category=ToolCategory.WEB,
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="搜索关键词",
                    required=True
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="最大结果数",
                    required=False
                )
            ],
            returns={
                "type": "object",
                "properties": {
                    "results": {"type": "array", "description": "搜索结果"},
                    "summary": {"type": "string", "description": "结果摘要"}
                }
            }
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行网络搜索操作

        Args:
            **kwargs: 包含搜索参数的字典
                - query (str): 搜索关键词，默认为空字符串
                - max_results (int): 最大返回结果数量，默认为3

        Returns:
            Dict[str, Any]: 搜索结果，包含以下字段：
                - results: 搜索到的结果列表
                - summary: 对搜索结果的简要总结
        """
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 3)

        # 模拟搜索
        results = await self._simulate_search(query, max_results)

        return {
            "results": results,
            "summary": f"找到{len(results)}个关于'{query}'的信息。"
        }

    async def _simulate_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        模拟网络搜索过程并返回预设结果

        Args:
            query (str): 用户输入的搜索关键词
            max_results (int): 需要返回的最大结果数量

        Returns:
            List[Dict[str, Any]]: 符合查询条件的模拟搜索结果列表
        """
        await asyncio.sleep(0.5)  # 模拟网络延迟

        # 模拟搜索结果
        mock_results = {
            "物流成本": [
                {
                    "title": "2024年物流运输成本分析",
                    "snippet": "受油价和人工成本影响，今年物流运输成本预计上涨10-15%。",
                    "source": "物流新闻",
                    "date": "2024-01-15"
                },
                {
                    "title": "海运价格波动趋势",
                    "snippet": "国际海运价格在年初有所回落，但预计下半年将小幅上涨。",
                    "source": "航运报告",
                    "date": "2024-01-10"
                }
            ],
            "绿色物流": [
                {
                    "title": "国家绿色物流发展规划",
                    "snippet": "到2025年，新能源物流车占比将达到30%，绿色包装使用率超过80%。",
                    "source": "政策文件",
                    "date": "2024-01-20"
                }
            ]
        }

        # 查找匹配的模拟结果
        for key, results in mock_results.items():
            if key in query:
                return results[:max_results]

        # 默认返回
        return [
            {
                "title": f"关于'{query}'的搜索结果",
                "snippet": f"这是关于{query}的搜索结果。",
                "source": "搜索引擎",
                "date": datetime.now().strftime("%Y-%m-%d")
            }
        ][:max_results]


class WeatherCheckTool(BaseTool):
    """天气检查工具"""

    def get_schema(self) -> ToolSchema:
        """
        获取天气检查工具的元数据定义

        Returns:
            ToolSchema: 工具的结构化描述，包括名称、描述、分类、参数和返回值格式
        """
        return ToolSchema(
            name="weather_check",
            description="检查特定地区的天气情况，用于物流路线规划和风险预警",
            category=ToolCategory.WEB,
            parameters=[
                ToolParameter(
                    name="location",
                    type="string",
                    description="城市或地区名称",
                    required=True
                ),
                ToolParameter(
                    name="forecast_days",
                    type="integer",
                    description="预报天数",
                    required=False
                )
            ],
            returns={
                "type": "object",
                "properties": {
                    "current_weather": {"type": "object", "description": "当前天气"},
                    "forecast": {"type": "array", "description": "天气预报"},
                    "logistics_impact": {"type": "string", "description": "对物流的影响"}
                }
            }
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行天气检查操作

        Args:
            **kwargs: 包含位置和预报天数的参数字典
                - location (str): 要查询的城市或地区名称，默认为空字符串
                - forecast_days (int): 天气预报的天数，默认为3天

        Returns:
            Dict[str, Any]: 天气信息及对物流的影响评估，包含以下字段：
                - current_weather: 当前天气状况
                - forecast: 未来几天的天气预报
                - logistics_impact: 分析得出的天气对物流运输的影响
                - location: 查询的位置信息
        """
        location = kwargs.get("location", "")
        forecast_days = kwargs.get("forecast_days", 3)

        # 模拟天气数据
        weather_data = await self._simulate_weather(location, forecast_days)

        return {
            "current_weather": weather_data["current"],
            "forecast": weather_data["forecast"],
            "logistics_impact": self._analyze_logistics_impact(weather_data),
            "location": location
        }

    async def _simulate_weather(self, location: str, forecast_days: int) -> Dict[str, Any]:
        """
        模拟获取指定地点的天气数据

        Args:
            location (str): 地理位置名称
            forecast_days (int): 预报天数

        Returns:
            Dict[str, Any]: 包含当前天气和未来预报的数据字典
        """
        await asyncio.sleep(0.3)

        import random

        weather_conditions = ["晴", "多云", "阴", "小雨", "中雨", "大雨", "雾", "霾"]

        current_weather = {
            "condition": random.choice(weather_conditions),
            "temperature": random.randint(0, 30),
            "humidity": random.randint(30, 90),
            "wind_speed": random.randint(0, 15)
        }

        # 生成预报
        forecast = []
        for i in range(forecast_days):
            forecast_date = datetime.now() + timedelta(days=i)
            forecast.append({
                "date": forecast_date.strftime("%Y-%m-%d"),
                "condition": random.choice(weather_conditions),
                "high_temp": random.randint(15, 30),
                "low_temp": random.randint(5, 20)
            })

        return {
            "current": current_weather,
            "forecast": forecast
        }

    def _analyze_logistics_impact(self, weather_data: Dict[str, Any]) -> str:
        """
        根据天气数据分析其对物流运输可能造成的影响

        Args:
            weather_data (Dict[str, Any]): 包含当前天气状态的字典

        Returns:
            str: 描述天气对物流影响的文字说明
        """
        current = weather_data["current"]
        condition = current.get("condition", "")
        wind_speed = current.get("wind_speed", 0)

        impacts = []

        if condition in ["大雨", "暴雨"]:
            impacts.append("恶劣天气可能导致运输延迟")
        if condition == "雾":
            impacts.append("大雾天气影响高速公路运输安全")
        if wind_speed > 10:
            impacts.append("大风天气影响空运和海运")

        if not impacts:
            impacts.append("天气状况良好，对物流运输无明显影响")

        return "；".join(impacts)
