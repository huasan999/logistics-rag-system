"""
计算工具类
提供物流相关的各种计算功能
提供的计算功能包括：
- 运输成本计算：根据距离、重量、运输方式等计算运输成本，函数名：transport_cost_calculator
- 配送时间计算：根据距离、运输速度等计算配送时间，函数名：delivery_time_calculator
- 经济订货批量计算：根据需求频率、单位成本、固定成本等计算经济订货批量，函数名：eoq_calculator
"""
import math
from typing import Dict, Any
from datetime import datetime, timedelta

from src.tools.base_tool import BaseTool, ToolSchema, ToolParameter, ToolCategory


class LogisticsCalculatorTool(BaseTool):
    """物流计算器"""

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="logistics_calculator",
            description="计算各种物流相关的指标，如运输成本、库存成本、配送时间等",
            category=ToolCategory.CALCULATOR,
            parameters=[
                ToolParameter(
                    name="calculation_type",
                    type="string",
                    description="计算类型：transport_cost（运输成本）、delivery_time（配送时间）、eoq（经济订货批量）",
                    required=True
                ),
                ToolParameter(
                    name="parameters",
                    type="object",
                    description="计算参数，根据不同的计算类型提供不同的参数",
                    required=True
                )
            ],
            returns={
                "type": "object",
                "properties": {
                    "result": {"type": "number", "description": "计算结果"},
                    "unit": {"type": "string", "description": "单位"},
                    "explanation": {"type": "string", "description": "计算解释"}
                }
            }
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        calculation_type = kwargs.get("calculation_type")
        params = kwargs.get("parameters", {})

        try:
            if calculation_type == "transport_cost":
                return await self._calculate_transport_cost(params)
            elif calculation_type == "delivery_time":
                return await self._calculate_delivery_time(params)
            elif calculation_type == "eoq":
                return await self._calculate_eoq(params)
            else:
                raise ValueError(f"未知的计算类型: {calculation_type}")

        except Exception as e:
            return {
                "error": str(e),
                "result": None,
                "unit": "",
                "explanation": f"计算失败: {str(e)}"
            }

    async def _calculate_transport_cost(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """计算运输成本"""
        distance = params.get("distance", 0)  # 公里
        weight = params.get("weight", 0)  # 公斤
        volume = params.get("volume", 0)  # 立方米
        transport_type = params.get("transport_type", "truck")  # 运输方式

        # 基础费率（元/公里·吨）
        base_rates = {
            "truck": 2.5,      # 公路运输
            "rail": 0.8,       # 铁路运输
            "air": 8.0,        # 航空运输
            "sea": 0.3         # 海运
        }

        if transport_type not in base_rates:
            transport_type = "truck"

        # 计算计费重量（按实际重量和体积重量取大值）
        volumetric_weight = volume * 250  # 1立方米 = 250公斤
        chargeable_weight = max(weight, volumetric_weight)

        # 计算成本
        base_cost = distance * base_rates[transport_type] * (chargeable_weight / 1000)

        # 附加费用
        additional_costs = {
            "fuel_surcharge": base_cost * 0.1,  # 燃油附加费 10%
            "highway_toll": distance * 0.5,     # 高速费
            "loading_fee": 50 if weight > 0 else 0  # 装卸费
        }

        total_cost = base_cost + sum(additional_costs.values())

        return {
            "result": round(total_cost, 2),
            "unit": "元",
            "explanation": f"运输成本计算：距离{distance}公里，重量{weight}kg，体积{volume}m³，运输方式{transport_type}。总成本{round(total_cost, 2)}元。"
        }

    async def _calculate_delivery_time(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """计算配送时间"""
        distance = params.get("distance", 0)  # 公里
        transport_type = params.get("transport_type", "truck")

        # 不同运输方式的平均速度（公里/小时）
        speeds = {
            "truck": 60,    # 卡车
            "rail": 40,     # 铁路
            "air": 800,     # 航空
            "sea": 25       # 海运
        }

        if transport_type not in speeds:
            transport_type = "truck"

        # 基础运输时间
        travel_time = distance / speeds[transport_type]

        # 附加时间（小时）
        additional_times = {
            "loading_unloading": 2,
            "customs_clearance": 24 if transport_type in ["air", "sea"] else 0,
            "transfer": 4 if distance > 500 else 0
        }

        total_hours = travel_time + sum(additional_times.values())

        # 转换为天和小时
        days = int(total_hours // 24)
        hours = int(total_hours % 24)

        return {
            "result": total_hours,
            "unit": "小时",
            "explanation": f"配送时间估算：距离{distance}公里，运输方式{transport_type}。预计需要{days}天{hours}小时。"
        }

    async def _calculate_eoq(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """计算经济订货批量（EOQ）"""
        annual_demand = params.get("annual_demand", 0)      # 年需求量
        order_cost = params.get("order_cost", 0)           # 每次订货成本
        holding_cost_per_unit = params.get("holding_cost_per_unit", 0)  # 单位持有成本

        if annual_demand <= 0 or order_cost <= 0 or holding_cost_per_unit <= 0:
            raise ValueError("参数必须大于0")

        # EOQ公式：√(2DS/H)
        eoq = math.sqrt((2 * annual_demand * order_cost) / holding_cost_per_unit)

        # 计算相关指标
        optimal_orders = annual_demand / eoq
        time_between_orders = 365 / optimal_orders

        return {
            "result": round(eoq),
            "unit": "件",
            "explanation": f"经济订货批量计算：年需求量{annual_demand}件，订货成本{order_cost}元/次，单位持有成本{holding_cost_per_unit}元/件。建议每次订货{round(eoq)}件，每年订货{round(optimal_orders, 1)}次。"
        }


class UnitConverterTool(BaseTool):
    """单位转换工具"""

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="unit_converter",
            description="转换物流相关的单位，如重量、体积、距离等",
            category=ToolCategory.CALCULATOR,
            parameters=[
                ToolParameter(
                    name="value",
                    type="number",
                    description="要转换的数值",
                    required=True
                ),
                ToolParameter(
                    name="from_unit",
                    type="string",
                    description="原单位",
                    required=True
                ),
                ToolParameter(
                    name="to_unit",
                    type="string",
                    description="目标单位",
                    required=True
                ),
                ToolParameter(
                    name="unit_type",
                    type="string",
                    description="单位类型：weight（重量）、length（长度）",
                    required=True
                )
            ],
            returns={
                "type": "object",
                "properties": {
                    "converted_value": {"type": "number", "description": "转换后的值"},
                    "explanation": {"type": "string", "description": "转换解释"}
                }
            }
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        value = kwargs.get("value", 0)
        from_unit = kwargs.get("from_unit", "").lower()
        to_unit = kwargs.get("to_unit", "").lower()
        unit_type = kwargs.get("unit_type", "weight")

        # 转换表
        conversion_tables = {
            "weight": {
                "kg": 1,
                "g": 0.001,
                "ton": 1000,
                "lb": 0.453592,
                "oz": 0.0283495
            },
            "length": {
                "km": 1,
                "m": 0.001,
                "cm": 0.00001,
                "mi": 1.60934,
                "yd": 0.0009144,
                "ft": 0.0003048
            }
        }

        if unit_type not in conversion_tables:
            raise ValueError(f"不支持的单位类型: {unit_type}")

        table = conversion_tables[unit_type]

        if from_unit not in table or to_unit not in table:
            raise ValueError(f"不支持的单位转换: {from_unit} -> {to_unit}")

        # 转换为基准单位，再转换到目标单位
        value_in_base = value * table[from_unit]
        converted_value = value_in_base / table[to_unit]

        return {
            "converted_value": round(converted_value, 4),
            "explanation": f"{value}{from_unit} = {round(converted_value, 4)}{to_unit}"
        }