"""
增强版RAG管道
整合Function Call和RAG检索
"""
import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.rag_pipeline import RAGPipeline
from src.function_caller import FunctionCaller, FunctionCallMode
from src.tool_registry import get_tool_registry


logger = logging.getLogger(__name__)


class EnhancedRAGPipeline:
    """增强版RAG管道"""

    def __init__(
        self,
        rag_pipeline: RAGPipeline,
        function_caller: FunctionCaller,
        tool_registry=None,
        mode: FunctionCallMode = FunctionCallMode.AUTO
    ):
        self.rag_pipeline = rag_pipeline
        self.tool_registry = tool_registry or get_tool_registry()
        self.function_caller = function_caller
        self.mode = mode

        logger.info(f"增强RAG管道初始化，函数调用模式: {mode.value}")

    async def query(self, question: str, conversation_context: str = "", **kwargs) -> Dict[str, Any]:
        """增强查询（支持对话上下文）"""
        try:
            logger.info(f"增强查询: {question}")

            # 无论是否需要函数调用，都先获取相关文档用于返回
            relevant_docs = self.rag_pipeline.retriever.invoke(question)

            # 格式化文档信息（确保即使函数调用失败也有来源信息）
            rag_sources = []
            for doc in relevant_docs:
                rag_sources.append({
                    "content": doc.page_content[:300] + ("..." if len(doc.page_content) > 300 else ""),
                    "source": doc.metadata.get("source", "未知来源"),
                    "chunk_id": doc.metadata.get("chunk_id", "N/A")
                })

            # 1. 检测是否需要函数调用
            need_function_call, suggested_tool = self.function_caller.detect_function_call_intent(question)

            # 2. 根据模式决定
            if self.mode == FunctionCallMode.NEVER:
                need_function_call = False
            elif self.mode == FunctionCallMode.ALWAYS:
                need_function_call = True

            # 3. 不需要函数调用，直接使用RAG
            if not need_function_call:
                logger.info("未检测到函数调用需求，使用基础RAG")
                rag_result = await self.rag_pipeline.query(question, conversation_context)
                # 确保有来源信息
                if not rag_result.get("rag_sources"):
                    rag_result["rag_sources"] = rag_sources
                    rag_result["source_count"] = len(relevant_docs)
                return rag_result

            # 4. 需要函数调用，解析并执行
            logger.info("检测到函数调用需求，开始解析...")
            function_call = await self.function_caller.parse_function_call(question)

            if not function_call:
                logger.info("函数调用解析失败，回退到基础RAG")
                rag_result = await self.rag_pipeline.query(question, conversation_context)
                # 确保有来源信息
                if not rag_result.get("rag_sources"):
                    rag_result["rag_sources"] = rag_sources
                    rag_result["source_count"] = len(relevant_docs)
                return rag_result

            # 5. 执行函数调用
            logger.info(f"执行函数调用: {function_call.get('name')}")
            execution_result = await self.function_caller.execute_function_call(function_call)

            if not execution_result.get("success"):
                logger.warning("函数调用执行失败，回退到基础RAG")
                rag_result = await self.rag_pipeline.query(question, conversation_context)
                # 确保有来源信息
                if not rag_result.get("rag_sources"):
                    rag_result["rag_sources"] = rag_sources
                    rag_result["source_count"] = len(relevant_docs)
                return rag_result

            # 6. 获取工具结果
            tool_result = execution_result.get("result", {})

            # 判断是否需要结合RAG上下文和对话上下文
            need_rag_context = self._needs_rag_context(question, function_call)

            if need_rag_context:
                # 获取RAG结果（传入对话上下文）
                rag_result = await self.rag_pipeline.query(question, conversation_context)
                rag_context = self._format_rag_context(rag_result)

                # 整合结果（考虑对话上下文）
                integrated_answer = await self._integrate_results(
                    question, function_call, tool_result, rag_context, conversation_context
                )

                return {
                    "question": question,
                    "answer": integrated_answer,
                    "type": "integrated",
                    "function_call": function_call,
                    "tool_result": tool_result,
                    "rag_sources": rag_result.get("rag_sources", rag_sources),  # 优先使用RAG来源
                    "source_count": rag_result.get("source_count", len(relevant_docs)),
                    "has_conversation_context": bool(conversation_context),
                    "timestamp": datetime.now().isoformat(),
                    "status": "success"
                }
            else:
                # 直接返回工具结果（但可能仍然需要考虑对话上下文）
                answer = self._format_tool_answer(question, function_call, tool_result, conversation_context)

                return {
                    "question": question,
                    "answer": answer,
                    "type": "function_call",
                    "function_call": function_call,
                    "tool_result": tool_result,
                    "rag_sources": rag_sources,  # 即使不需要RAG上下文，也返回相关文档
                    "source_count": len(relevant_docs),
                    "has_conversation_context": bool(conversation_context),
                    "timestamp": datetime.now().isoformat(),
                    "status": "success"
                }

        except Exception as e:
            logger.error(f"增强查询失败: {e}")
            # 回退到基础RAG
            try:
                rag_result = await self.rag_pipeline.query(question, conversation_context)
                return rag_result
            except Exception as rag_error:
                logger.error(f"基础RAG回退失败: {rag_error}")
                return {
                    "question": question,
                    "answer": f"抱歉，处理过程中出现错误：{str(e)}",
                    "type": "error",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e),
                    "status": "error",
                    "rag_sources": [],  # 即使错误也返回空数组
                    "source_count": 0
                }

    def _needs_rag_context(self, question: str, function_call: Dict[str, Any]) -> bool:
        """判断是否需要RAG上下文"""
        tool_name = function_call.get("name", "")

        # 某些工具不需要RAG上下文
        no_rag_tools = [
            "unit_converter",
            "weather_check",
            "logistics_tracking"
        ]

        if tool_name in no_rag_tools:
            return False

        # 查询类工具可能需要RAG上下文
        if tool_name in ["logistics_query", "web_search"]:
            return True

        # 根据问题复杂度判断
        question_words = len(question.split())
        if question_words > 10:  # 复杂问题需要更多上下文
            return True

        return False

    def _format_rag_context(self, rag_result: Dict[str, Any]) -> str:
        """格式化RAG上下文"""
        if not rag_result.get("rag_sources"):
            return "没有找到相关的上下文信息。"

        context_parts = ["相关上下文信息："]
        for i, source in enumerate(rag_result["rag_sources"][:3], 1):
            content = source.get("content", "")[:200]
            context_parts.append(f"{i}. {content}...")

        return "\n".join(context_parts)

    async def _integrate_results(self, question: str, function_call: Dict[str, Any],
                                     tool_result: Dict[str, Any], rag_context: str,
                                     conversation_context: str = "") -> str:
            """整合工具结果和RAG上下文（考虑对话上下文）"""
            # 构建整合提示
            if conversation_context:
                integration_prompt = ChatPromptTemplate.from_messages([
                    ("system", """你是一个物流专家，需要结合工具执行结果、专业知识和对话历史回答问题。

    对话历史：
    {conversation_context}

    工具执行结果：
    {tool_result}

    专业知识：
    {rag_context}

    请综合分析，给出专业、准确的回答。"""),
                    ("human", "{question}")
                ])
            else:
                integration_prompt = ChatPromptTemplate.from_messages([
                    ("system", """你是一个物流专家，需要结合工具执行结果和专业知识回答问题。

    工具执行结果：
    {tool_result}

    专业知识：
    {rag_context}

    请综合分析，给出专业、准确的回答。"""),
                    ("human", "{question}")
                ])

            # 格式化工具结果
            formatted_tool_result = self._format_tool_result(tool_result)

            # 调用LLM生成整合回答
            integration_chain = (
                    integration_prompt
                    | self.function_caller.llm
                    | StrOutputParser()
            )

            try:
                if conversation_context:
                    integrated_answer = await integration_chain.ainvoke({
                        "tool_result": formatted_tool_result,
                        "rag_context": rag_context,
                        "conversation_context": conversation_context,
                        "question": question
                    })
                else:
                    integrated_answer = await integration_chain.ainvoke({
                        "tool_result": formatted_tool_result,
                        "rag_context": rag_context,
                        "question": question
                    })
                return integrated_answer
            except Exception as e:
                logger.error(f"结果整合失败: {e}")
                # 回退到工具结果
                return self._format_tool_answer(question, function_call, tool_result, conversation_context)

    def _format_tool_result(self, tool_result: Dict[str, Any]) -> str:
        """格式化工具结果"""
        if "error" in tool_result:
            return f"工具执行错误: {tool_result['error']}"

        if "explanation" in tool_result:
            return tool_result["explanation"]
        elif "answer" in tool_result:
            return tool_result["answer"]
        elif "summary" in tool_result:
            return tool_result["summary"]
        else:
            return json.dumps(tool_result, ensure_ascii=False, indent=2)

    def _format_tool_answer(self, question: str, function_call: Dict[str, Any],
                            tool_result: Dict[str, Any], conversation_context: str = "") -> str:
        """格式化工具答案（考虑对话上下文）"""
        tool_name = function_call.get("name", "")

        # 如果有对话上下文，可以在回答中提及
        context_note = ""
        if conversation_context:
            context_note = "\n\n（注：已考虑之前的对话历史）\n"

        # 根据不同工具类型格式化答案
        if tool_name == "logistics_calculator":
            if "explanation" in tool_result:
                return f"根据您的需求，我已经完成了计算：\n\n{tool_result['explanation']}{context_note}"

        elif tool_name == "unit_converter":
            if "explanation" in tool_result:
                return f"单位转换结果：{tool_result['explanation']}{context_note}"

        elif tool_name == "logistics_query":
            if "answer" in tool_result:
                return f"{tool_result['answer']}{context_note}"

        elif tool_name == "shipping_rate_query":
            if "recommendation" in tool_result:
                return f"运费查询完成：\n\n{tool_result['recommendation']}{context_note}"

        elif tool_name == "weather_check":
            if "logistics_impact" in tool_result:
                return f"天气查询结果：{tool_result['logistics_impact']}{context_note}"

        # 默认格式
        if "explanation" in tool_result:
            return f"{tool_result['explanation']}{context_note}"
        elif "answer" in tool_result:
            return f"{tool_result['answer']}{context_note}"
        else:
            return f"工具'{tool_name}'执行完成。{context_note}"

    async def stream_query(self, question: str, conversation_context: str = ""):
        """流式查询（支持对话上下文）- 改进版"""
        try:
            logger.info(f"增强流式查询: {question}")

            # 获取完整结果（包含来源信息）
            result = await self.query(question, conversation_context)
            answer = result.get("answer", "")
            sources = result.get("rag_sources", [])

            # 分块发送答案
            chunk_size = 50
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i + chunk_size]
                yield {"type": "chunk", "content": chunk}

            # 发送来源信息
            if sources:
                yield {"type": "sources", "sources": sources}

        except Exception as e:
            logger.error(f"增强流式查询失败: {e}")
            yield {"type": "error", "content": f"错误：{str(e)}"}


def create_enhanced_rag_pipeline(
    rag_pipeline: RAGPipeline,
    function_caller: FunctionCaller,
    mode: FunctionCallMode = FunctionCallMode.AUTO
) -> EnhancedRAGPipeline:
    """创建增强版RAG管道"""
    return EnhancedRAGPipeline(rag_pipeline, function_caller, mode=mode)