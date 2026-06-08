"""
函数调用器
处理LLM的函数调用逻辑
"""
# 导入所需的Python标准库和第三方库
import json          # 用于JSON数据的解析和序列化
import logging       # 日志记录模块
import re           # 正则表达式模块
from typing import Dict, Any, Optional, Tuple  # 类型注解支持
from enum import Enum  # 枚举类型支持

# 导入LangChain库中的Ollama语言模型类
from langchain_community.llms import Ollama

# 导入本地工具注册表模块
from src.tool_registry import get_tool_registry

# 创建日志记录器实例
logger = logging.getLogger(__name__)

class FunctionCallMode(str, Enum):
    """函数调用模式枚举类，定义了三种不同的函数调用策略"""
    AUTO = "auto"          # 自动判断是否调用函数
    ALWAYS = "always"      # 总是尝试调用函数
    NEVER = "never"        # 从不调用函数

class FunctionCaller:
    """函数调用器类，负责检测、解析和执行工具函数调用"""

    def __init__(
        self,
        llm: Ollama,
        tool_registry=None,
        mode: FunctionCallMode = FunctionCallMode.AUTO
    ):
        """
        初始化函数调用器

        Args:
            llm: 使用的语言模型实例，用于解析用户意图
            tool_registry: 工具注册表，默认使用全局注册表
            mode: 函数调用模式，默认为自动判断
        """
        # 存储语言模型实例
        self.llm = llm
        # 获取或设置工具注册表
        self.tool_registry = tool_registry or get_tool_registry()
        # 设置函数调用模式
        self.mode = mode

    def detect_function_call_intent(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        检测用户查询是否需要函数调用

        通过关键字匹配的方式分析用户问题，判断是否需要调用特定工具函数

        Args:
            query: 用户查询字符串

        Returns:
            元组(需要函数调用, 推荐的工具名称)
        """
        # 将查询转换为小写以便统一匹配
        query_lower = query.lower()

        # 检测计算意图相关的关键字
        calculation_keywords = [
            "calculate", "compute", "how much", "cost", "price",
            "estimate", "what is the", "多少", "计算", "费用"
        ]

        # 如果匹配到计算相关关键字
        if any(keyword in query_lower for keyword in calculation_keywords):
            # 进一步检查具体计算类型
            if any(word in query_lower for word in ["运输", "transport", "shipping", "运费"]):
                return True, "logistics_calculator"  # 返回运输计算器工具
            elif any(word in query_lower for word in ["转换", "convert", "unit"]):
                return True, "unit_converter"       # 返回单位转换工具

        # 检测查询意图关键字（如定义、解释等）
        query_keywords = ["what is", "define", "explain", "meaning of", "是什么", "定义", "解释"]
        if any(keyword in query_lower for keyword in query_keywords):
            return True, "logistics_query"          # 返回物流查询工具

        # 检测跟踪意图关键字
        tracking_keywords = ["track", "status", "where is", "delivery", "运单", "跟踪"]
        if any(keyword in query_lower for keyword in tracking_keywords):
            return True, "logistics_tracking"       # 返回物流跟踪工具

        # 检测搜索意图关键字
        search_keywords = ["search", "find", "latest", "news", "search for", "搜索"]
        if any(keyword in query_lower for keyword in search_keywords):
            return True, "web_search"               # 返回网络搜索工具

        # 检测天气意图关键字
        weather_keywords = ["weather", "forecast", "rain", "snow", "天气", "预报"]
        if any(keyword in query_lower for keyword in weather_keywords):
            return True, "weather_check"            # 返回天气检查工具

        # 检测运费查询关键字
        if any(word in query_lower for word in ["rate", "quote", "报价", "运费"]):
            return True, "shipping_rate_query"      # 返回运费查询工具

        # 根据预设模式决定是否需要函数调用
        if self.mode == FunctionCallMode.ALWAYS:
            return True, None
        elif self.mode == FunctionCallMode.NEVER:
            return False, None
        else:  # AUTO模式
            return False, None

    async def parse_function_call(self, query: str) -> Optional[Dict[str, Any]]:
        """
        解析用户查询中的函数调用信息

        使用语言模型分析用户问题，提取需要调用的工具函数及其参数

        Args:
            query: 用户查询字符串

        Returns:
            函数调用信息字典或None（如果没有检测到函数调用）
        """
        # 检测是否需要函数调用及推荐工具
        need_call, suggested_tool = self.detect_function_call_intent(query)

        # 如果不需要函数调用，直接返回None
        if not need_call:
            return None

        # 构建提示词用于语言模型分析
        prompt = self._build_function_call_prompt(query, suggested_tool)

        try:
            # 调用语言模型解析函数调用
            response = await self.llm.ainvoke(prompt)

            # 从响应中提取函数调用信息
            function_call = self._extract_function_call(response)

            # 如果成功提取到函数调用信息
            if function_call:
                logger.info(f"检测到函数调用: {function_call.get('name')}")
                return function_call
            else:
                logger.info("未检测到函数调用")
                return None

        except Exception as e:
            # 记录解析失败的错误信息
            logger.error(f"函数调用解析失败: {e}")
            return None

    def _build_function_call_prompt(self, query: str, suggested_tool: Optional[str] = None) -> str:
        """
        构建用于函数调用分析的提示词

        为语言模型提供结构化指导，帮助其识别和提取函数调用信息

        Args:
            query: 用户查询
            suggested_tool: 建议使用的工具名称（可选）

        Returns:
            构造好的提示词文本
        """
        # 获取所有可用工具的信息
        tools_info = self._get_tools_info()

        # 构建基础提示词
        prompt = f"""你是一个物流智能助手，需要根据用户的问题判断是否需要调用工具函数。

可用工具列表：
{tools_info}

用户问题：{query}

请分析用户问题，如果需要调用工具，请按照以下JSON格式回复：
{{
    "need_function_call": true,
    "function_name": "工具名称",
    "parameters": {{
        "参数1": "值1",
        "参数2": "值2"
    }}
}}

如果不需要调用工具，回复：
{{
    "need_function_call": false
}}

请确保参数值从用户问题中提取，如果用户没有提供必要参数，请使用合理的默认值。
"""

        # 如果有推荐工具，添加提示信息
        if suggested_tool:
            prompt += f"\n提示：这个问题可能适合使用'{suggested_tool}'工具。\n"

        return prompt

    def _get_tools_info(self) -> str:
        """
        获取所有注册工具的信息字符串

        格式化输出所有可用工具的名称、描述和参数信息

        Returns:
            格式化的工具信息字符串
        """
        tools_info = []

        # 遍历所有注册的工具
        for tool_name, tool in self.tool_registry.tools.items():
            schema = tool.schema
            # 提取参数名称列表
            params = ", ".join([p.name for p in schema.parameters])
            # 格式化工具信息
            tools_info.append(f"- {tool_name}: {schema.description} (参数: {params})")

        return "\n".join(tools_info)

    def _extract_function_call(self, response: str) -> Optional[Dict[str, Any]]:
        """
        从语言模型响应中提取函数调用信息

        使用正则表达式解析响应中的JSON数据，提取函数调用相关信息

        Args:
            response: 语言模型的原始响应字符串

        Returns:
            提取的函数调用信息字典或None
        """
        try:
            # 使用正则表达式查找响应中的JSON数据
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                # 解析JSON数据
                data = json.loads(json_match.group())
                # 如果标记为需要函数调用
                if data.get("need_function_call", False):
                    # 返回标准化的函数调用信息
                    return {
                        "name": data.get("function_name"),
                        "arguments": data.get("parameters", {})
                    }
        except json.JSONDecodeError:
            # 记录JSON解析错误
            logger.warning("无法解析JSON响应")

        return None

    async def execute_function_call(self, function_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行函数调用

        根据提取的函数调用信息，实际调用相应的工具函数

        Args:
            function_call: 函数调用信息字典

        Returns:
            执行结果字典
        """
        # 提取工具名称和参数
        tool_name = function_call.get("name")
        arguments = function_call.get("arguments", {})

        # 检查工具名称是否存在
        if not tool_name:
            return {"error": "函数名称为空"}

        # 执行工具函数
        result = await self.tool_registry.execute_tool(tool_name, **arguments)

        # 返回执行结果信息
        return {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "success": "error" not in result  # 根据是否有错误字段判断执行是否成功
        }

    async def process_with_function_call(self, query: str) -> Dict[str, Any]:
        """
        处理带函数调用的完整查询流程

        整合函数调用检测、解析和执行的全过程

        Args:
            query: 用户查询字符串

        Returns:
            处理结果字典
        """
        # 解析函数调用信息
        function_call = await self.parse_function_call(query)

        # 如果没有检测到函数调用
        if not function_call:
            return {
                "type": "direct_response",
                "query": query,
                "function_call": None,
                "result": None
            }

        # 执行函数调用
        execution_result = await self.execute_function_call(function_call)

        # 根据执行结果整合返回信息
        if execution_result.get("success"):
            # 执行成功，返回成功信息和摘要
            return {
                "type": "function_call",
                "query": query,
                "function_call": function_call,
                "execution_result": execution_result,
                "summary": self._generate_function_call_summary(function_call, execution_result)
            }
        else:
            # 执行失败，返回错误信息
            return {
                "type": "function_call_error",
                "query": query,
                "function_call": function_call,
                "error": execution_result.get("result", {}).get("error", "未知错误")
            }

    def _generate_function_call_summary(self, function_call: Dict[str, Any],
                                       execution_result: Dict[str, Any]) -> str:
        """
        生成函数调用结果摘要

        从执行结果中提取关键信息，生成简洁的摘要文本

        Args:
            function_call: 函数调用信息
            execution_result: 执行结果

        Returns:
            生成的摘要文本
        """
        # 获取工具名称
        tool_name = function_call.get("name", "未知工具")
        # 获取执行结果数据
        result = execution_result.get("result", {})

        # 根据结果中不同字段生成摘要
        if "explanation" in result:
            return result["explanation"]
        elif "answer" in result:
            return result["answer"][:200] + "..."  # 截取前200字符
        elif "summary" in result:
            return result["summary"]
        else:
            return f"工具'{tool_name}'执行完成"


# 测试函数
async def test_function_caller():
    """测试函数调用器"""
    caller = FunctionCaller()

    test_queries = [
        "计算从上海到北京的运输成本，距离1200公里，重量500公斤",
        "什么是FOB？",
        "跟踪运单SF123456789",
        "将100公斤转换为磅",
        "查询上海的天气",
        "今天美元对人民币的汇率是多少？"
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        result = await caller.process_with_function_call(query)

        if result["type"] == "function_call":
            print(f"工具调用: {result['function_call']['name']}")
            print(f"摘要: {result['summary']}")
        else:
            print("未调用工具")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_function_caller())