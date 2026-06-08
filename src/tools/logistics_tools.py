"""
物流专业工具类
提供物流行业特有的功能和查询
提供的物流专业工具包括：
- 物流术语查询：查询物流行业中的专业术语解释，函数名：logistics_query
- 物流流程说明：说明物流行业中的具体流程和操作步骤，函数名：logistics_flow
- 运输成本计算：根据距离、重量、运输方式等计算运输成本，函数名：transport_cost_calculator
- 物流信息跟踪：查询物流行业中的运输信息，如运单状态、物流轨迹等，函数名：logistics_tracking
"""
import re
from typing import Dict, Any, List
from datetime import datetime, timedelta

from src.tools.base_tool import BaseTool, ToolSchema, ToolParameter, ToolCategory


class LogisticsQueryTool(BaseTool):
    """物流信息查询工具"""

    def get_schema(self) -> ToolSchema:
        """
        获取工具的定义结构

        Returns:
            ToolSchema: 工具的定义结构，包括名称、描述、分类、参数和返回值
        """
        return ToolSchema(
            name="logistics_query",
            description="查询物流相关的专业知识，如术语解释、流程说明等",
            category=ToolCategory.LOGISTICS,
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="查询内容，如术语名称、流程名称等",
                    required=True
                ),
                ToolParameter(
                    name="detail_level",
                    type="string",
                    description="详细程度：brief（简要）、detailed（详细）",
                    required=False
                )
            ],
            returns={
                "type": "object",
                "properties": {
                    "answer": {"type": "string", "description": "查询结果"},
                    "source": {"type": "string", "description": "信息来源"}
                }
            }
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行物流术语查询操作

        Args:
            **kwargs: 包含查询参数的字典
                - query (str): 查询关键词
                - detail_level (str): 结果详细程度，默认为"detailed"

        Returns:
            Dict[str, Any]: 查询结果，包含答案和来源
        """
        query = kwargs.get("query", "")
        detail_level = kwargs.get("detail_level", "detailed")

        # 内置物流知识库
        knowledge_base = self._get_knowledge_base()

        results = []
        for item in knowledge_base:
            if self._matches_query(item, query):
                results.append(item)

        if not results:
            return {
                "answer": f"未找到关于'{query}'的信息。",
                "source": "知识库"
            }

        # 根据详细程度格式化答案
        answer = self._format_answer(results, detail_level)

        return {
            "answer": answer,
            "source": "物流知识库"
        }

    def _get_knowledge_base(self) -> List[Dict[str, Any]]:
        """
        获取内置知识库

        Returns:
            List[Dict[str, Any]]: 物流术语知识库列表
        """
        return [
            {
                "term": "FOB",
                "definition": "Free On Board（船上交货），国际贸易术语。卖方在指定装运港将货物交到买方指定的船上，即完成交货。卖方承担货物越过船舷前的一切费用和风险。",
                "related": ["CIF", "EXW", "FCA"]
            },
            {
                "term": "CIF",
                "definition": "Cost, Insurance and Freight（成本加保险费加运费），卖方负责租船订舱、支付运费和保险费，承担货物在装运港越过船舷前的风险。",
                "related": ["FOB", "CFR", "CIP"]
            },
            {
                "term": "物流",
                "definition": "物品从供应地向接收地的实体流动过程。根据实际需要，将运输、储存、装卸、搬运、包装、流通加工、配送、信息处理等基本功能实施有机结合。",
                "related": ["供应链", "运输", "仓储"]
            },
            {
                "term": "第三方物流",
                "definition": "Third-Party Logistics (3PL)，由独立于买卖双方的第三方专业公司提供物流服务的业务模式。包括运输、仓储、配送、信息管理等服务。",
                "related": ["物流外包", "合同物流", "供应链管理"]
            },
            {
                "term": "仓储管理",
                "definition": "对仓库和库存进行有效管理的活动。包括入库管理、在库管理、出库管理、库存控制、货位管理等。",
                "related": ["WMS", "库存管理", "仓库布局"]
            }
        ]

    def _matches_query(self, item: Dict[str, Any], query: str) -> bool:
        """
        检查项目是否匹配查询

        Args:
            item (Dict[str, Any]): 知识库中的条目
            query (str): 查询字符串

        Returns:
            bool: 是否匹配
        """
        query_lower = query.lower()
        term_lower = item["term"].lower()

        # 检查完全匹配或部分匹配
        return query_lower in term_lower or term_lower in query_lower

    def _format_answer(self, results: List[Dict[str, Any]], detail_level: str) -> str:
        """
        格式化答案

        Args:
            results (List[Dict[str, Any]]): 匹配的结果列表
            detail_level (str): 详细程度

        Returns:
            str: 格式化后的答案
        """
        if detail_level == "brief":
            return results[0].get("definition", "")[:100] + "..."
        else:
            result = results[0]
            answer = f"{result.get('term', '查询结果')}：{result.get('definition', '')}"
            if result.get("related"):
                answer += f"\n\n相关术语：{', '.join(result['related'])}"
            return answer


class ShippingRateTool(BaseTool):
    """运费查询工具"""

    def get_schema(self) -> ToolSchema:
        """
        获取工具的定义结构

        Returns:
            ToolSchema: 工具的定义结构，包括名称、描述、分类、参数和返回值
        """
        return ToolSchema(
            name="shipping_rate_query",
            description="查询不同运输方式的运费报价",
            category=ToolCategory.LOGISTICS,
            parameters=[
                ToolParameter(
                    name="origin",
                    type="string",
                    description="始发地",
                    required=True
                ),
                ToolParameter(
                    name="destination",
                    type="string",
                    description="目的地",
                    required=True
                ),
                ToolParameter(
                    name="cargo_details",
                    type="object",
                    description="货物详情 {weight, volume}",
                    required=True
                ),
                ToolParameter(
                    name="transport_mode",
                    type="string",
                    description="运输方式：air（空运）、sea（海运）、land（陆运）",
                    required=True
                )
            ],
            returns={
                "type": "object",
                "properties": {
                    "rates": {"type": "array", "description": "运费报价"},
                    "recommendation": {"type": "string", "description": "推荐方案"}
                }
            }
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行运费查询操作

        Args:
            **kwargs: 包含查询参数的字典
                - origin (str): 始发地
                - destination (str): 目的地
                - cargo_details (dict): 货物详情，包含重量和体积
                - transport_mode (str): 运输方式

        Returns:
            Dict[str, Any]: 运费报价和推荐方案
        """
        origin = kwargs.get("origin", "")
        destination = kwargs.get("destination", "")
        cargo_details = kwargs.get("cargo_details", {})
        transport_mode = kwargs.get("transport_mode", "land")

        # 模拟运费查询
        weight = cargo_details.get("weight", 0)
        volume = cargo_details.get("volume", 0)

        # 计算运费
        rates = self._calculate_rates(origin, destination, weight, volume, transport_mode)

        return {
            "rates": rates,
            "recommendation": f"从{origin}到{destination}的{transport_mode}运输，预计费用{rates[0]['cost']}元，时效{rates[0]['transit_time']}天。"
        }

    def _calculate_rates(self, origin: str, destination: str, weight: float,
                        volume: float, mode: str) -> List[Dict[str, Any]]:
        """
        计算运费

        Args:
            origin (str): 始发地
            destination (str): 目的地
            weight (float): 货物重量
            volume (float): 货物体积
            mode (str): 运输方式

        Returns:
            List[Dict[str, Any]]: 运费报价列表
        """
        # 模拟距离
        distance = self._estimate_distance(origin, destination)

        if mode == "air":
            cost = weight * 15 + distance * 0.1
            transit_time = max(1, distance / 2000)
        elif mode == "sea":
            cost = volume * 500 + distance * 0.05
            transit_time = max(7, distance / 500)
        else:  # land
            cost = weight * 2 + distance * 0.5
            transit_time = max(2, distance / 500)

        return [{
            "carrier": f"模拟{mode}运输公司",
            "mode": mode,
            "cost": round(cost, 2),
            "transit_time": round(transit_time, 1),
            "currency": "CNY"
        }]

    def _estimate_distance(self, origin: str, destination: str) -> float:
        """
        估计两地之间的距离

        Args:
            origin (str): 始发地
            destination (str): 目的地

        Returns:
            float: 估算的距离（公里）
        """
        distances = {
            ("上海", "北京"): 1200,
            ("上海", "广州"): 1400,
            ("北京", "广州"): 2100,
            ("上海", "深圳"): 1300
        }

        key = (origin, destination)
        reverse_key = (destination, origin)

        if key in distances:
            return distances[key]
        elif reverse_key in distances:
            return distances[reverse_key]

        return 800  # 默认距离


class TrackingTool(BaseTool):
    """物流跟踪工具"""

    def get_schema(self) -> ToolSchema:
        """
        获取工具的定义结构

        Returns:
            ToolSchema: 工具的定义结构，包括名称、描述、分类、参数和返回值
        """
        return ToolSchema(
            name="logistics_tracking",
            description="查询物流运单的实时状态和位置信息",
            category=ToolCategory.LOGISTICS,
            parameters=[
                ToolParameter(
                    name="tracking_number",
                    type="string",
                    description="运单号",
                    required=True
                ),
                ToolParameter(
                    name="carrier",
                    type="string",
                    description="承运商：sf（顺丰）、yto（圆通）、sto（申通）",
                    required=True
                )
            ],
            returns={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "当前状态"},
                    "current_location": {"type": "string", "description": "当前位置"},
                    "estimated_delivery": {"type": "string", "description": "预计送达时间"}
                }
            }
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行物流跟踪操作

        Args:
            **kwargs: 包含查询参数的字典
                - tracking_number (str): 运单号
                - carrier (str): 承运商代码

        Returns:
            Dict[str, Any]: 物流跟踪信息
        """
        tracking_number = kwargs.get("tracking_number", "")
        carrier = kwargs.get("carrier", "sf")

        # 模拟跟踪数据
        tracking_data = self._simulate_tracking(tracking_number, carrier)

        return {
            "status": tracking_data["status"],
            "current_location": tracking_data["current_location"],
            "estimated_delivery": tracking_data["estimated_delivery"],
            "carrier": carrier,
            "tracking_number": tracking_number
        }

    def _simulate_tracking(self, tracking_number: str, carrier: str) -> Dict[str, Any]:
        """
        模拟物流跟踪数据

        Args:
            tracking_number (str): 运单号
            carrier (str): 承运商代码

        Returns:
            Dict[str, Any]: 模拟的物流跟踪数据
        """
        import random

        # 模拟状态
        statuses = [
            {"status": "已收件", "location": "上海分拨中心"},
            {"status": "运输中", "location": "上海-南京高速"},
            {"status": "到达中转站", "location": "南京分拨中心"},
            {"status": "派送中", "location": "南京市鼓楼区"},
            {"status": "已签收", "location": "收件人地址"}
        ]

        # 随机选择一个状态
        current_status = random.choice(statuses)

        # 预计送达时间
        if current_status["status"] == "已签收":
            estimated_delivery = "已送达"
        else:
            days = random.randint(1, 3)
            estimated_delivery = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

        return {
            "status": current_status["status"],
            "current_location": current_status["location"],
            "estimated_delivery": estimated_delivery
        }
