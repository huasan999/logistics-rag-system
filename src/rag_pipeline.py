"""
RAG管道模块
负责检索增强生成的全流程
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

from src.llm_manager import LLMManager
from src.vector_store import VectorStoreManager


logger = logging.getLogger(__name__)


class RAGPipeline:
    """RAG管道类，用于构建和管理基于检索增强生成（RAG）的问答流程。

    该类整合了语言模型与向量数据库，提供标准查询和流式查询功能，
    支持带对话上下文的理解能力。
    """

    def __init__(self, llm_manager: LLMManager, vector_store_manager: VectorStoreManager):
        """初始化RAG管道实例。

        Args:
            llm_manager: 大语言模型管理器对象，用于获取LLM实例。
            vector_store_manager: 向量存储管理器对象，用于获取文档检索器。
        """
        self.llm_manager = llm_manager
        self.vector_store_manager = vector_store_manager
        self.llm = llm_manager.get_llm()
        self.retriever = vector_store_manager.get_retriever()
        self.rag_chain = self._create_rag_chain()
        self.rag_chain_with_context = self._create_rag_chain_with_context()

        logger.info("RAG管道初始化完成")

    def _create_rag_chain(self):
        """创建基础RAG链，不包含对话上下文。

        使用系统提示模板结合用户问题和检索到的上下文信息进行推理，
        并通过语言模型生成最终答案。

        Returns:
            构造好的LangChain可运行链对象。
        """
        # 定义提示模板
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的物流行业顾问，请基于提供的上下文信息回答问题。
            
上下文信息：
{context}

请准确、专业地回答用户问题。如果上下文信息不足，请如实告知。"""),
            ("human", "{question}")
        ])

        # 文档格式化函数
        def format_docs(docs):
            formatted = []
            for i, doc in enumerate(docs, 1):
                content = doc.page_content
                source = doc.metadata.get("source", "未知来源")
                formatted.append(f"[{i}] {content}\n来源: {source}\n")
            return "\n".join(formatted)

        # 构建RAG链
        rag_chain = (
            {
                "context": self.retriever | RunnableLambda(format_docs),
                "question": RunnablePassthrough(),
                "current_time": RunnableLambda(lambda _: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            }
            | prompt_template
            | self.llm
            | StrOutputParser()
        )

        return rag_chain

    def _create_rag_chain_with_context(self):
        """创建带有对话上下文的RAG链。

        在基础RAG的基础上增加了对话历史的支持，使得模型能够理解多轮对话中
        的语境关系并作出更精准的回答。

        Returns:
            带有对话上下文处理能力的LangChain可运行链对象。
        """
        # 定义提示模板（包含对话上下文）
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的物流行业顾问，请基于提供的上下文信息和对话历史回答问题。

    对话历史：
    {conversation_context}

    上下文信息：
    {context}

    请准确、专业地回答用户问题。如果上下文信息不足，请如实告知。
    注意：对话历史中的内容可能包含之前的对话摘要，请参考这些信息来更好地理解当前问题。"""),
            ("human", "{question}")
        ])

        # 文档格式化函数
        def format_docs(docs):
            formatted = []
            for i, doc in enumerate(docs, 1):
                content = doc.page_content
                source = doc.metadata.get("source", "未知来源")
                formatted.append(f"[{i}] {content}\n来源: {source}\n")
            return "\n".join(formatted)

        # 构建RAG链
        rag_chain = (
                {
                    "context": self.retriever | RunnableLambda(format_docs),
                    "conversation_context": RunnablePassthrough(),
                    "question": RunnablePassthrough(),
                    "current_time": RunnableLambda(lambda _: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                }
                | prompt_template
                | self.llm
                | StrOutputParser()
        )

        return rag_chain

    async def query(self, question: str, conversation_context: str = "", **kwargs) -> Dict[str, Any]:
        """执行一次完整的RAG查询操作，并返回结构化的响应结果。

        Args:
            question: 用户提出的问题字符串。
            conversation_context: 可选的对话上下文字符串，默认为空表示单次提问。

        Returns:
            包含问题、答案、引用源等详细信息的结果字典。
        """
        try:
            logger.info(f"执行查询: {question}")

            # 检索相关文档
            relevant_docs = self.retriever.invoke(question)

            # 生成答案（根据是否有对话上下文选择不同的链）
            if conversation_context:
                answer = await self.rag_chain_with_context.ainvoke({
                    "question": question,
                    "conversation_context": conversation_context
                })
            else:
                answer = await self.rag_chain.ainvoke(question)

            # 构建结果
            result = {
                "question": question,
                "answer": answer,
                "rag_sources": [
                    {
                        "content": doc.page_content[:300] + ("..." if len(doc.page_content) > 300 else ""),
                        "source": doc.metadata.get("source", "未知来源"),
                        "chunk_id": doc.metadata.get("chunk_id", "N/A")
                    }
                    for doc in relevant_docs
                ],
                "source_count": len(relevant_docs),
                "type": "basic_rag",
                "has_conversation_context": bool(conversation_context),
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            }

            logger.info(f"查询完成, 找到 {len(relevant_docs)} 个相关文档")
            return result

        except Exception as e:
            logger.error(f"查询失败: {e}")
            return {
                "question": question,
                "answer": f"抱歉，查询过程中出现错误：{str(e)}",
                "rag_sources": [],
                "source_count": 0,
                "type": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "status": "error"
            }

    async def stream_query(self, question: str, conversation_context: str = ""):
        """以流式方式执行RAG查询，逐段输出生成的答案内容。"""
        try:
            # 构建流式提示
            if conversation_context:
                prompt_template = ChatPromptTemplate.from_messages([
                    ("system", """你是一个专业的物流行业顾问，请基于提供的上下文信息和对话历史回答问题。

    对话历史：
    {conversation_context}

    上下文信息：
    {context}

    请准确、专业地回答用户问题。"""),
                    ("human", "{question}")
                ])
            else:
                prompt_template = ChatPromptTemplate.from_messages([
                    ("system", """你是一个专业的物流行业顾问，请基于提供的上下文信息回答问题。

    上下文信息：
    {context}

    请准确、专业地回答用户问题。"""),
                    ("human", "{question}")
                ])

            # 检索相关文档
            relevant_docs = self.retriever.invoke(question)

            # 格式化文档
            def format_docs(docs):
                formatted = []
                for i, doc in enumerate(docs, 1):
                    content = doc.page_content[:200] + ("..." if len(doc.page_content) > 200 else "")
                    source = doc.metadata.get("source", "未知来源")
                    formatted.append(f"[{i}] {content}")
                return "\n".join(formatted)

            # 构建流式链
            if conversation_context:
                rag_chain = (
                        {
                            "context": RunnableLambda(lambda _: format_docs(relevant_docs)),
                            "conversation_context": RunnableLambda(lambda _: conversation_context),
                            "question": RunnablePassthrough(),
                        }
                        | prompt_template
                        | self.llm
                )
            else:
                rag_chain = (
                        {
                            "context": RunnableLambda(lambda _: format_docs(relevant_docs)),
                            "question": RunnablePassthrough(),
                        }
                        | prompt_template
                        | self.llm
                )

            # 流式输出
            async for chunk in rag_chain.astream(question):
                if hasattr(chunk, 'content'):
                    yield chunk.content
                else:
                    yield str(chunk)

        except Exception as e:
            logger.error(f"流式查询失败: {e}")
            yield f"错误：{str(e)}"

def create_rag_pipeline(llm_manager: LLMManager, vector_store_manager: VectorStoreManager):
    """创建RAG管道的工厂函数。

    Args:
        llm_manager: 语言模型管理器实例。
        vector_store_manager: 向量存储管理器实例。

    Returns:
        初始化后的RAGPipeline对象。
    """
    return RAGPipeline(llm_manager, vector_store_manager)
