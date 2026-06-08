"""
Web API模块
提供RESTful API接口和自动生成的API文档
"""
import asyncio
import logging
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, Path, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field, validator
import uvicorn

from src.llm_manager import LLMManager
from src.vector_store import VectorStoreManager
from src.document_processor import DocumentProcessor
from src.rag_pipeline import create_rag_pipeline
from src.tool_registry import get_tool_registry
from src.function_caller import FunctionCaller, FunctionCallMode
from src.enhanced_rag import create_enhanced_rag_pipeline
from src.conversation_manager import get_conversation_manager
from src.config import get_config_manager

logger = logging.getLogger(__name__)
# ==================== 数据模型定义 ====================

class QueryRequest(BaseModel):
    """查询请求模型"""
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="用户的问题",
        example="什么是FOB贸易术语？"
    )
    session_id: Optional[str] = Field(
        None,
        description="会话ID，用于对话上下文管理",
        example="session_123456789"
    )
    stream: bool = Field(
        False,
        description="是否使用流式响应",
        example=True
    )

    @validator('question')
    def question_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('问题不能为空')
        return v.strip()

class QueryResponse(BaseModel):
    """查询响应模型"""
    question: str = Field(..., description="用户的问题")
    answer: str = Field(..., description="系统的回答")
    rag_sources: List[dict] = Field([], description="参考的知识库文档")
    source_count: int = Field(0, description="参考文档数量")
    status: str = Field(..., description="响应状态", example="success")
    timestamp: str = Field(..., description="响应时间戳")
    session_id: Optional[str] = Field(None, description="会话ID")
    function_call: Optional[dict] = Field(None, description="函数调用信息")
    tool_result: Optional[dict] = Field(None, description="工具执行结果")
    response_type: str = Field("direct", description="响应类型")
    conversation_stats: Optional[dict] = Field(None, description="对话统计信息")

class ToolInfo(BaseModel):
    """工具信息模型"""
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    category: str = Field(..., description="工具类别")

class SystemInfo(BaseModel):
    """系统信息模型"""
    status: str = Field(..., description="系统状态")
    version: str = Field(..., description="系统版本")
    provider: str = Field(..., description="模型提供商")
    llm_model: str = Field(..., description="LLM模型")
    embedding_model: str = Field(..., description="嵌入模型")
    function_call_enabled: bool = Field(..., description="是否启用函数调用")
    function_call_mode: str = Field(..., description="函数调用模式")
    document_count: int = Field(0, description="知识库文档数量")
    mode: str = Field(..., description="系统模式")
    uptime: str = Field(..., description="运行时间")

class ConversationStats(BaseModel):
    """对话统计模型"""
    session_id: str = Field(..., description="会话ID")
    message_count: int = Field(0, description="消息数量")
    has_summary: bool = Field(False, description="是否有摘要")
    summary_version: int = Field(0, description="摘要版本")
    last_summary_time: Optional[str] = Field(None, description="最后生成摘要时间")

class ExampleQuery(BaseModel):
    """示例查询模型"""
    question: str = Field(..., description="示例问题")
    description: str = Field(..., description="问题描述")
    category: str = Field(..., description="问题类别")

class HealthCheck(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="健康状态")
    timestamp: str = Field(..., description="检查时间")
    service: str = Field(..., description="服务名称")
    version: str = Field(..., description="服务版本")

class ErrorResponse(BaseModel):
    """错误响应模型"""
    detail: str = Field(..., description="错误详情")
    error_code: Optional[str] = Field(None, description="错误代码")
    timestamp: str = Field(..., description="错误时间")

# ==================== WebSocket管理器 ====================

from typing import List
from fastapi import WebSocket

class ConnectionManager:
    """WebSocket连接管理器

    管理多个WebSocket连接，提供连接建立、断开和消息发送功能
    """

    def __init__(self):
        """初始化连接管理器

        创建一个空的活跃连接列表用于存储所有已建立的WebSocket连接
        """
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """接受并建立新的WebSocket连接

        参数:
            websocket (WebSocket): 需要建立连接的WebSocket对象
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """断开指定的WebSocket连接

        从活跃连接列表中移除指定的WebSocket连接

        参数:
            websocket (WebSocket): 需要断开的WebSocket对象
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, websocket: WebSocket, message: dict):
        """向指定的WebSocket连接发送JSON消息

        参数:
            websocket (WebSocket): 目标WebSocket连接
            message (dict): 要发送的JSON格式消息
        """
        await websocket.send_json(message)

# ==================== 物流RAG系统 ====================

class LogisticsRAGSystem:
    """
    物流RAG系统

    负责整合语言模型、向量数据库、工具调用等功能，
    实现基于检索增强生成（RAG）的智能问答与对话功能。
    """

    def __init__(self):
        """
        初始化物流RAG系统

        设置配置项、启动时间，并初始化各核心组件。
        包括LLM管理器、向量存储、文档处理器等。
        """
        self.config = get_config_manager().get_config()
        self.start_time = datetime.now()

        # 初始化组件占位符
        self.llm_manager = None
        self.vector_store_manager = None
        self.document_processor = None
        self.tool_registry = None
        self.rag_pipeline = None
        self.function_caller = None
        self.enhanced_pipeline = None

        # 初始化对话管理器
        self.conversation_manager = get_conversation_manager(self.config)

        self._initialize_components()

    def _initialize_components(self):
        """
        初始化所有系统组件

        按顺序初始化以下模块：
        1. LLM管理器
        2. 向量存储管理器
        3. 文档处理模块并构建向量库
        4. 工具注册表（如启用函数调用）
        5. RAG基础管道
        6. 增强型RAG管道（如启用且为增强模式）

        异常处理确保初始化过程中的错误被捕获并上报。
        """
        logger.info("初始化系统组件...")

        try:
            # 1. 初始化LLM管理器
            self.llm_manager = LLMManager(self.config)

            # 2. 初始化向量存储
            self.vector_store_manager = VectorStoreManager(self.config)

            # 3. 处理知识库
            self.document_processor = DocumentProcessor(self.config)
            documents = self.document_processor.process_knowledge_base()

            if documents:
                self.vector_store_manager.get_or_create_vectorstore(documents)
                logger.info(f"知识库加载完成: {len(documents)} 个文档块")

            # 4. 初始化工具系统
            if self.config.rag.enable_function_call:
                self.tool_registry = get_tool_registry(self.config.tools)
                logger.info(f"工具系统初始化完成: {len(self.tool_registry.tools)} 个工具")

            # 5. 创建RAG管道
            self.rag_pipeline = create_rag_pipeline(self.llm_manager, self.vector_store_manager)

            # 6. 创建增强管道（如果需要）
            if self.config.rag.enable_function_call and self.config.system.mode == "enhanced":
                mode_map = {
                    "auto": FunctionCallMode.AUTO,
                    "always": FunctionCallMode.ALWAYS,
                    "never": FunctionCallMode.NEVER
                }
                mode = mode_map.get(self.config.rag.function_call_mode, FunctionCallMode.AUTO)

                self.function_caller = FunctionCaller(
                    llm=self.llm_manager.get_llm(),
                    tool_registry=self.tool_registry,
                    mode=mode
                )

                self.enhanced_pipeline = create_enhanced_rag_pipeline(
                    self.rag_pipeline,
                    self.function_caller,
                    mode=mode
                )
                logger.info(f"增强RAG管道初始化完成，模式: {mode.value}")

            logger.info("系统初始化完成")

        except Exception as e:
            logger.error(f"系统初始化失败: {e}")
            raise

    def get_pipeline(self):
        """
        获取当前使用的查询管道

        根据是否启用了增强模式返回对应的管道实例。

        Returns:
            object: 当前可用的查询管道对象（增强或基础）
        """
        if self.enhanced_pipeline:
            return self.enhanced_pipeline
        return self.rag_pipeline

    def get_vector_store_info(self):
        """
        获取向量存储的基本信息

        包含文档总数和集合名称。若无法访问则返回默认值及错误信息。

        Returns:
            dict: 包含文档数量、集合名等信息的字典
        """
        if self.vector_store_manager and self.vector_store_manager.vectorstore:
            try:
                collection = self.vector_store_manager.vectorstore._collection
                count = collection.count()
                return {
                    "document_count": count,
                    "collection_name": self.config.vector_store.collection_name
                }
            except Exception as e:
                logger.error(f"获取向量存储信息失败: {e}")
                return {"document_count": 0, "error": str(e)}
        return {"document_count": 0}

    async def query(self, question: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行一次完整的问答请求

        参数:
            question (str): 用户提出的问题
            session_id (Optional[str]): 对话会话标识符，默认自动生成

        返回:
            Dict[str, Any]: 包含答案、状态、统计数据等的结果字典
        """
        # 确保有session_id
        if not session_id:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"创建新会话: {session_id}")

        logger.info(f"=== 查询开始 ===")
        logger.info(f"会话ID: {session_id}")
        logger.info(f"问题: {question}")

        # 添加用户消息到对话历史
        logger.info(f"添加用户消息到对话 {session_id}")
        self.conversation_manager.add_message(session_id, "user", question)

        # 立即检查消息是否添加成功
        conversation = self.conversation_manager.get_or_create_conversation(session_id)
        logger.info(f"添加用户消息后，对话 {session_id} 消息数: {len(conversation.messages)}")

        # 获取对话上下文
        conversation_context = self.conversation_manager.get_conversation_context(session_id)
        logger.info(f"对话上下文长度: {len(conversation_context)}")

        # 构建增强的问题（包含对话上下文）
        enhanced_question = f"{conversation_context}\n\n当前问题：{question}"

        # 获取管道并执行查询
        pipeline = self.get_pipeline()

        try:
            # 执行查询
            result = await pipeline.query(enhanced_question, conversation_context)

            # 添加助手回答到对话历史
            if result.get("answer"):
                logger.info(f"添加助手消息到对话 {session_id}")
                self.conversation_manager.add_message(session_id, "assistant", result.get("answer"))

                # 再次检查消息数量
                conversation = self.conversation_manager.get_or_create_conversation(session_id)
                logger.info(f"添加助手消息后，对话 {session_id} 消息数: {len(conversation.messages)}")

            # 检查是否需要生成摘要
            if self._should_generate_summary(session_id):
                logger.info(f"对话 {session_id} 达到生成摘要条件")
                try:
                    asyncio.create_task(
                        self._safe_generate_summary(session_id),
                        name=f"summary_{session_id}"
                    )
                except Exception as e:
                    logger.error(f"创建摘要生成任务失败: {e}")

            # 获取对话统计
            stats = self.conversation_manager.get_stats(session_id)
            result["conversation_stats"] = stats
            result["session_id"] = session_id

            logger.info(f"查询完成，会话 {session_id} 最终消息数: {stats['message_count']}")
            logger.info("=== 查询结束 ===")

            return result

        except Exception as e:
            logger.error(f"查询失败: {e}")
            return {
                "question": question,
                "answer": f"抱歉，查询过程中出现错误：{str(e)}",
                "type": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "status": "error",
                "session_id": session_id
            }

    async def stream_query(self, question: str, conversation_context: str = "", session_id: str = None):
        """
        流式执行问答请求

        支持实时输出结果片段，并在完成后将完整回答加入对话历史。

        参数:
            question (str): 用户提出的问题
            conversation_context (str): 上下文对话内容，默认为空字符串
            session_id (str): 对话会话标识符，默认为None

        Yields:
            dict or str: 输出流式响应数据包
        """
        try:
            logger.info(f"流式查询开始: {question}, 会话ID: {session_id}")

            # 如果有session_id，添加用户消息到对话历史
            full_answer = ""
            sources = []

            if session_id:
                logger.info(f"流式查询添加用户消息: {session_id}")
                self.conversation_manager.add_message(session_id, "user", question)

                # 获取更新后的对话上下文
                conversation_context = self.conversation_manager.get_conversation_context(session_id)
                logger.info(f"流式查询对话上下文长度: {len(conversation_context)}")

                # 立即获取当前消息数并记录
                conversation = self.conversation_manager.get_or_create_conversation(session_id)
                logger.info(f"用户消息添加后，会话 {session_id} 当前消息数: {len(conversation.messages)}")

            # 获取管道
            pipeline = self.get_pipeline()

            # 收集流式回答
            if hasattr(pipeline, 'stream_query'):
                # 使用增强管道的流式查询
                async for chunk in pipeline.stream_query(question, conversation_context):
                    if isinstance(chunk, dict):
                        if chunk.get("type") == "chunk":
                            content = chunk.get("content", "")
                            full_answer += content
                            yield {"type": "chunk", "content": content}
                        elif chunk.get("type") == "sources":
                            sources = chunk.get("sources", [])
                            yield {"type": "sources", "sources": sources}
                        else:
                            yield chunk
                    else:
                        full_answer += str(chunk)
                        yield {"type": "chunk", "content": str(chunk)}
            else:
                # 回退到基础RAG管道的流式查询
                async for chunk in self.rag_pipeline.stream_query(question, conversation_context):
                    full_answer += chunk
                    yield {"type": "chunk", "content": chunk}

                # 获取相关文档
                try:
                    relevant_docs = self.vector_store_manager.get_retriever().invoke(question)
                    sources = []
                    for doc in relevant_docs:
                        sources.append({
                            "content": doc.page_content[:300] + ("..." if len(doc.page_content) > 300 else ""),
                            "source": doc.metadata.get("source", "未知来源"),
                            "chunk_id": doc.metadata.get("chunk_id", "N/A")
                        })

                    if sources:
                        yield {"type": "sources", "sources": sources}
                except Exception as e:
                    logger.error(f"获取来源失败: {e}")

            # 流式查询结束后，添加助手消息并检查摘要
            if session_id and full_answer:
                logger.info(f"流式查询结束，添加助手消息到对话 {session_id}")
                self.conversation_manager.add_message(session_id, "assistant", full_answer)

                # 获取最终消息数
                conversation = self.conversation_manager.get_or_create_conversation(session_id)
                final_count = len(conversation.messages)
                logger.info(f"助手消息添加后，会话 {session_id} 最终消息数: {final_count}")

                # 检查是否需要生成摘要
                if self._should_generate_summary(session_id):
                    logger.info(f"对话 {session_id} 达到生成摘要条件")
                    try:
                        asyncio.create_task(
                            self._safe_generate_summary(session_id),
                            name=f"summary_{session_id}"
                        )
                    except Exception as e:
                        logger.error(f"创建摘要生成任务失败: {e}")

                # 返回最终消息数
                yield {
                    "type": "conversation_stats",
                    "message_count": final_count,
                    "session_id": session_id
                }

        except Exception as e:
            logger.error(f"流式查询失败: {e}")
            yield {"type": "error", "content": f"错误：{str(e)}"}

    def _should_generate_summary(self, session_id: str) -> bool:
        """
        判断是否应该为指定会话生成摘要

        根据配置中设定的最小消息数和间隔来决定是否触发摘要生成逻辑。

        参数:
            session_id (str): 会话唯一标识符

        Returns:
            bool: 是否应生成摘要
        """
        try:
            conversation = self.conversation_manager.get_or_create_conversation(session_id)
            message_count = len(conversation.messages)

            # 使用配置的阈值
            summary_min_messages = getattr(self.config.conversation, 'summary_min_messages', 10)

            # 检查是否达到生成摘要的条件
            if message_count >= summary_min_messages:
                # 检查距离上次生成摘要的消息数
                if conversation.summary_version == 0:
                    return True

                # 后续检查：距离上次摘要的消息数达到阈值
                summary_interval = getattr(self.config.conversation, 'summary_interval', 5)
                if message_count - (conversation.summary_version * summary_interval) >= summary_interval:
                    return True

            return False
        except Exception as e:
            logger.error(f"检查是否需要生成摘要失败: {e}")
            return False

    async def _safe_generate_summary(self, session_id: str):
        """
        安全地异步生成对话摘要

        在后台运行以避免阻塞主流程，同时捕获异常防止崩溃。

        参数:
            session_id (str): 需要生成摘要的会话ID
        """
        try:
            summary = await self.conversation_manager.generate_summary(session_id)
            if summary:
                logger.info(f"对话 {session_id} 摘要生成成功")
            else:
                logger.debug(f"对话 {session_id} 未生成摘要")
        except Exception as e:
            logger.error(f"生成对话摘要失败: {e}")

    def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统的整体运行信息

        包括版本号、模型类型、运行时长、文档数量等关键指标。

        Returns:
            Dict[str, Any]: 系统基本信息组成的字典
        """
        uptime = str(datetime.now() - self.start_time)

        # 获取向量存储信息
        vector_info = self.get_vector_store_info()

        provider = self.config.models.provider.lower()
        llm_model = self.config.deepseek.model if provider == "deepseek" else self.config.models.llm

        return {
            "status": "running",
            "version": self.config.system.version,
            "provider": provider,
            "llm_model": llm_model,
            "embedding_model": self.config.models.embedding,
            "function_call_enabled": self.config.rag.enable_function_call,
            "function_call_mode": self.config.rag.function_call_mode,
            "document_count": vector_info.get("document_count", 0),
            "mode": self.config.system.mode,
            "uptime": uptime
        }

    def get_tools_info(self) -> List[ToolInfo]:
        """
        获取已注册的所有工具的信息列表

        Returns:
            List[ToolInfo]: 工具描述信息列表
        """
        if not self.tool_registry:
            return []

        tools = []
        for tool_name, tool in self.tool_registry.tools.items():
            schema = tool.schema
            tools.append(ToolInfo(
                name=tool_name,
                description=schema.description,
                category=schema.category.value
            ))

        return tools


# ==================== FastAPI应用创建 ====================

def create_app():
    """创建FastAPI应用"""
    app = FastAPI(
        title="物流智能问答系统 API",
        description="基于RAG和函数调用的物流行业智能问答系统 RESTful API",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        terms_of_service="http://example.com/terms/",
        contact={
            "name": "物流RAG系统开发团队",
            "url": "http://example.com/contact/",
            "email": "support@example.com",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
        openapi_tags=[
            {
                "name": "系统信息",
                "description": "系统状态和配置信息查询"
            },
            {
                "name": "知识库查询",
                "description": "物流知识库查询和问答"
            },
            {
                "name": "对话管理",
                "description": "对话历史管理和摘要生成"
            },
            {
                "name": "工具管理",
                "description": "可用工具查询和管理"
            },
            {
                "name": "WebSocket",
                "description": "实时WebSocket通信"
            },
            {
                "name": "健康检查",
                "description": "系统健康状态检查"
            }
        ]
    )

    # 自定义OpenAPI文档
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags
        )

        # 添加自定义信息
        openapi_schema["info"]["x-logo"] = {
            "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
        }

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载静态文件
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # 初始化系统
    system = LogisticsRAGSystem()
    connection_manager = ConnectionManager()

    # ==================== API端点定义 ====================
    @app.get(
        "/api/test/conversation",
        summary="测试对话功能",
        description="测试对话消息添加和统计功能",
        tags=["系统信息"]
    )
    async def test_conversation():
        """测试对话功能"""
        try:
            # 创建测试会话
            test_session_id = "test_session_" + datetime.now().strftime("%H%M%S")

            # 添加测试消息
            system.conversation_manager.add_message(test_session_id, "user", "测试用户消息1")
            system.conversation_manager.add_message(test_session_id, "assistant", "测试助手回复1")
            system.conversation_manager.add_message(test_session_id, "user", "测试用户消息2")
            system.conversation_manager.add_message(test_session_id, "assistant", "测试助手回复2")
            system.conversation_manager.add_message(test_session_id, "user", "测试用户消息3")
            system.conversation_manager.add_message(test_session_id, "assistant", "测试助手回复3")

            # 获取统计信息
            stats = system.conversation_manager.get_stats(test_session_id)

            # 获取对话
            conversation = system.conversation_manager.get_or_create_conversation(test_session_id)

            # 尝试生成摘要
            summary = await system.conversation_manager.generate_summary(test_session_id)

            return {
                "test_session_id": test_session_id,
                "stats": stats,
                "summary_result": summary[:100] + "..." if summary else "无摘要",
                "all_messages": [
                    {"role": msg.role, "content": msg.content[:50] + "..."}
                    for msg in conversation.messages
                ],
                "message_count": len(conversation.messages),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"测试对话功能失败: {e}")
            return {"error": str(e)}

    @app.get(
        "/debug",
        response_class=HTMLResponse,
        summary="调试页面",
        description="对话系统调试工具页面",
        tags=["系统信息"]
    )
    async def debug_page():
        """调试页面"""
        with open("templates/debug.html", "r", encoding="utf-8") as f:
            return f.read()

    @app.get(
        "/",
        response_class=HTMLResponse,
        summary="系统首页",
        description="返回系统Web界面首页",
        tags=["系统信息"]
    )
    async def root():
        """系统首页"""
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()

    @app.get(
        "/api/health",
        response_model=HealthCheck,
        summary="健康检查",
        description="检查系统健康状态",
        tags=["健康检查"],
        responses={
            200: {
                "description": "系统健康",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "healthy",
                            "timestamp": "2024-01-01T12:00:00Z",
                            "service": "物流智能问答系统",
                            "version": "2.0.0"
                        }
                    }
                }
            }
        }
    )
    async def health_check():
        """健康检查端点"""
        return HealthCheck(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            service="物流智能问答系统",
            version="2.0.0"
        )

    @app.get(
        "/api/info",
        response_model=SystemInfo,
        summary="获取系统信息",
        description="获取系统配置和状态信息",
        tags=["系统信息"],
        responses={
            200: {
                "description": "系统信息",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "running",
                            "version": "2.0.0",
                            "llm_model": "qwen2.5:7b",
                            "embedding_model": "nomic-embed-text",
                            "function_call_enabled": True,
                            "function_call_mode": "auto",
                            "document_count": 150,
                            "mode": "enhanced",
                            "uptime": "2 days, 3:45:12"
                        }
                    }
                }
            }
        }
    )
    async def get_system_info():
        """获取系统信息"""
        return SystemInfo(**system.get_system_info())

    @app.get(
        "/api/tools",
        summary="获取可用工具",
        description="获取所有可用的工具列表",
        tags=["工具管理"],
        responses={
            200: {
                "description": "工具列表",
                "content": {
                    "application/json": {
                        "example": {
                            "tools": [
                                {
                                    "name": "logistics_calculator",
                                    "description": "计算物流相关的指标",
                                    "category": "calculator"
                                }
                            ],
                            "count": 7
                        }
                    }
                }
            }
        }
    )
    async def get_available_tools():
        """获取可用工具"""
        tools = system.get_tools_info()
        return {"tools": tools, "count": len(tools)}

    @app.post(
        "/api/query",
        response_model=QueryResponse,
        summary="查询知识库",
        description="查询物流知识库并获取回答",
        tags=["知识库查询"],
        responses={
            200: {
                "description": "查询成功",
                "content": {
                    "application/json": {
                        "example": {
                            "question": "什么是FOB贸易术语？",
                            "answer": "FOB是国际贸易术语...",
                            "rag_sources": [
                                {
                                    "content": "FOB贸易术语的定义...",
                                    "source": "物流知识库",
                                    "chunk_id": 1
                                }
                            ],
                            "source_count": 1,
                            "status": "success",
                            "timestamp": "2024-01-01T12:00:00Z",
                            "session_id": "session_123456789",
                            "response_type": "direct"
                        }
                    }
                }
            },
            400: {
                "description": "请求参数错误",
                "model": ErrorResponse
            },
            500: {
                "description": "服务器内部错误",
                "model": ErrorResponse
            }
        }
    )
    async def query_knowledge_base(request: QueryRequest):
        """查询知识库"""
        try:
            # 执行查询
            result = await system.query(request.question, request.session_id)

            # 转换为响应格式
            return QueryResponse(
                question=result.get("question", request.question),
                answer=result.get("answer", ""),
                rag_sources=result.get("rag_sources", []),
                source_count=result.get("source_count", 0),
                status=result.get("status", "success"),
                timestamp=result.get("timestamp", datetime.now().isoformat()),
                session_id=result.get("session_id", request.session_id),
                function_call=result.get("function_call"),
                tool_result=result.get("tool_result"),
                response_type=result.get("type", "direct"),
                conversation_stats=result.get("conversation_stats")
            )

        except Exception as e:
            logger.error(f"查询失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(
        "/api/query/stream",
        summary="流式查询",
        description="使用流式响应查询知识库",
        tags=["知识库查询"],
        responses={
            200: {
                "description": "流式响应成功",
                "content": {
                    "text/event-stream": {
                        "example": "data: 这是流式回答的第一部分\n\ndata: 这是第二部分\n\n"
                    }
                }
            }
        }
    )
    async def stream_query(request: QueryRequest):
        """流式查询"""
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="问题不能为空")

        # 确保有session_id
        if not request.session_id:
            request.session_id = f"session_stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"流式查询创建新会话: {request.session_id}")

        async def generate():
            try:
                full_answer = ""
                sources = []
                conversation_context = ""

                if request.session_id:
                    conversation_context = system.conversation_manager.get_conversation_context(request.session_id)

                # 执行流式查询
                async for chunk in system.stream_query(
                        request.question,
                        conversation_context,
                        request.session_id
                ):
                    if chunk.get("type") == "chunk":
                        content = chunk.get("content", "")
                        full_answer += content
                        yield f"data: {content}\n\n"
                    elif chunk.get("type") == "sources":
                        sources = chunk.get("sources", [])
                        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
                    elif chunk.get("type") == "conversation_stats":
                        # 发送最终对话统计
                        stats = {
                            "type": "conversation_stats",
                            "message_count": chunk.get("message_count", 0),
                            "session_id": chunk.get("session_id", request.session_id)
                        }
                        # 获取完整的对话统计
                        full_stats = system.conversation_manager.get_stats(request.session_id)
                        stats.update(full_stats)
                        yield f"data: {json.dumps(stats)}\n\n"
                    elif chunk.get("type") == "error":
                        yield f"data: 错误: {chunk['content']}\n\n"

                # 流式结束
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"流式查询失败: {e}")
                yield f"data: 错误: {str(e)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    @app.get(
        "/api/examples",
        summary="获取示例查询",
        description="获取系统预置的示例查询问题",
        tags=["知识库查询"],
        responses={
            200: {
                "description": "示例查询列表",
                "content": {
                    "application/json": {
                        "example": {
                            "examples": [
                                {
                                    "question": "什么是FOB贸易术语？",
                                    "description": "查询物流术语定义",
                                    "category": "definition"
                                }
                            ],
                            "count": 5
                        }
                    }
                }
            }
        }
    )
    async def get_example_queries():
        """获取示例查询"""
        examples = [
            {
                "question": "什么是FOB贸易术语？",
                "description": "查询物流术语定义",
                "category": "definition"
            },
            {
                "question": "计算从上海到北京运输500公斤货物的成本，距离1200公里",
                "description": "运输成本计算",
                "category": "calculation"
            },
            {
                "question": "将100公斤转换为磅",
                "description": "单位转换",
                "category": "conversion"
            },
            {
                "question": "什么是第三方物流？",
                "description": "物流服务模式解释",
                "category": "definition"
            },
            {
                "question": "如何优化仓库库存管理？",
                "description": "综合建议",
                "category": "advice"
            }
        ]

        return {"examples": examples, "count": len(examples)}

    # ==================== 对话管理API ====================

    @app.get(
        "/api/conversation/{session_id}",
        response_model=ConversationStats,
        summary="获取对话信息",
        description="获取指定会话的对话统计信息",
        tags=["对话管理"],
        responses={
            200: {
                "description": "对话信息",
                "content": {
                    "application/json": {
                        "example": {
                            "session_id": "session_123456789",
                            "message_count": 10,
                            "has_summary": True,
                            "summary_version": 2,
                            "last_summary_time": "2024-01-01T12:00:00Z"
                        }
                    }
                }
            },
            404: {
                "description": "会话不存在",
                "model": ErrorResponse
            }
        }
    )
    async def get_conversation_info(
        session_id: str = Path(..., description="会话ID", example="session_123456789")
    ):
        """获取对话信息"""
        try:
            conversation_stats = system.conversation_manager.get_stats(session_id)
            return ConversationStats(**conversation_stats)
        except Exception as e:
            logger.error(f"获取对话信息失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(
        "/api/conversation/{session_id}/clear",
        summary="清空对话历史",
        description="清空指定会话的对话历史",
        tags=["对话管理"],
        responses={
            200: {
                "description": "清空成功",
                "content": {
                    "application/json": {
                        "example": {
                            "session_id": "session_123456789",
                            "status": "cleared",
                            "message": "对话历史已清空"
                        }
                    }
                }
            }
        }
    )
    async def clear_conversation(
        session_id: str = Path(..., description="会话ID", example="session_123456789")
    ):
        """清空对话历史"""
        try:
            system.conversation_manager.clear_conversation(session_id)
            return {
                "session_id": session_id,
                "status": "cleared",
                "message": "对话历史已清空"
            }
        except Exception as e:
            logger.error(f"清空对话失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(
        "/api/conversation/{session_id}/summary",
        summary="生成对话摘要",
        description="为指定会话生成对话摘要",
        tags=["对话管理"],
        responses={
            200: {
                "description": "摘要生成成功",
                "content": {
                    "application/json": {
                        "example": {
                            "session_id": "session_123456789",
                            "summary": "本次对话主要讨论了...",
                            "status": "success",
                            "timestamp": "2024-01-01T12:00:00Z"
                        }
                    }
                }
            }
        }
    )
    async def generate_summary(
            session_id: str = Path(..., description="会话ID", example="session_123456789")
    ):
        """生成对话摘要"""
        try:
            logger.info(f"摘要生成请求 - 会话ID: {session_id}")

            # 获取所有活跃会话
            all_sessions = list(system.conversation_manager.conversations.keys())
            logger.info(f"当前所有活跃会话: {all_sessions}")

            # 获取对话
            conversation = system.conversation_manager.get_or_create_conversation(session_id)

            # 检查消息数量
            min_messages = getattr(system.config.conversation, 'summary_min_messages', 10)
            message_count = len(conversation.messages)

            logger.info(f"会话 {session_id} 消息数量: {message_count} (需要至少 {min_messages} 条)")

            # 打印前几条消息
            for i, msg in enumerate(conversation.messages[:5]):
                logger.info(f"消息 {i + 1}: {msg.role} - {msg.content[:30]}...")

            if message_count < min_messages:
                return {
                    "session_id": session_id,
                    "summary": "",
                    "status": "failed",
                    "message": f"消息数量不足，至少需要{min_messages}条消息才能生成摘要，当前有{message_count}条",
                    "timestamp": datetime.now().isoformat()
                }

            # 检查LLM是否可用
            if not system.conversation_manager.summary_llm:
                return {
                    "session_id": session_id,
                    "summary": "",
                    "status": "failed",
                    "message": "LLM服务未初始化，无法生成摘要",
                    "timestamp": datetime.now().isoformat()
                }

            # 生成摘要
            summary = await system.conversation_manager.generate_summary(session_id)

            if summary:
                return {
                    "session_id": session_id,
                    "summary": summary,
                    "status": "success",
                    "message": "摘要生成成功",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "session_id": session_id,
                    "summary": "",
                    "status": "failed",
                    "message": "摘要生成失败，可能是对话内容不足或LLM服务异常",
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"生成摘要失败: {e}", exc_info=True)
            return {
                "session_id": session_id,
                "summary": "",
                "status": "failed",
                "message": f"生成摘要失败: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    @app.post(
        "/api/conversation/{session_id}/sync",
        summary="同步消息计数",
        description="同步前端和后端的消息计数",
        tags=["对话管理"]
    )
    async def sync_message_count(
            session_id: str = Path(..., description="会话ID"),
            sync_data: dict = Body(..., description="同步数据")
    ):
        """同步消息计数"""
        try:
            message_count = sync_data.get('message_count', 0)

            # 获取对话
            conversation = system.conversation_manager.get_or_create_conversation(session_id)

            # 如果服务器消息数量少于前端，记录差异
            server_count = len(conversation.messages)
            if message_count > server_count:
                logger.warning(f"消息计数不一致 - 会话: {session_id}, 前端: {message_count}, 后端: {server_count}")

            return {
                "session_id": session_id,
                "frontend_count": message_count,
                "backend_count": server_count,
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"同步消息计数失败: {e}")
            return {
                "session_id": session_id,
                "status": "failed",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }

    # 在 web_api.py 中添加
    @app.get("/api/conversation/{session_id}/realtime")
    async def get_realtime_conversation_stats(session_id: str):
        """获取实时对话统计（包含详细信息）"""
        try:
            conversation = system.conversation_manager.get_or_create_conversation(session_id)

            return {
                "session_id": session_id,
                "message_count": len(conversation.messages),
                "messages": [
                    {
                        "role": msg.role,
                        "content_preview": msg.content[:100] + ("..." if len(msg.content) > 100 else ""),
                        "timestamp": msg.timestamp
                    }
                    for msg in conversation.messages[-10:]  # 最近10条
                ],
                "has_summary": bool(conversation.summary),
                "summary_version": conversation.summary_version,
                "last_summary_time": conversation.last_summary_time,
                "summary_preview": conversation.summary[:200] + (
                    "..." if len(conversation.summary) > 200 else "") if conversation.summary else "",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取实时对话统计失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get(
        "/api/conversation/{session_id}/export",
        summary="导出对话历史",
        description="导出指定会话的完整对话历史",
        tags=["对话管理"],
        responses={
            200: {
                "description": "对话历史导出成功",
                "content": {
                    "application/json": {
                        "example": {
                            "session_id": "session_123456789",
                            "conversation": {
                                "messages": [
                                    {"role": "user", "content": "你好", "timestamp": "2024-01-01T12:00:00Z"}
                                ],
                                "summary": "对话摘要"
                            },
                            "status": "success"
                        }
                    }
                }
            }
        }
    )
    async def export_conversation(
        session_id: str = Path(..., description="会话ID", example="session_123456789")
    ):
        """导出对话历史"""
        try:
            conversation = system.conversation_manager.get_or_create_conversation(session_id)
            return {
                "session_id": session_id,
                "conversation": conversation.to_dict(),
                "status": "success"
            }
        except Exception as e:
            logger.error(f"导出对话失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get(
        "/api/debug/summary/{session_id}",
        summary="调试摘要服务",
        description="检查摘要生成服务的状态",
        tags=["系统信息"]
    )
    async def debug_summary_service(
            session_id: str = Path(..., description="会话ID", example="session_123456789")
    ):
        """调试摘要服务"""
        debug_info = system.conversation_manager.check_summary_service(session_id)

        # 检查Ollama服务
        ollama_status = "unknown"
        try:
            import requests
            response = requests.get(f"{system.config.ollama.base_url}/api/tags", timeout=5)
            ollama_status = "running" if response.status_code == 200 else f"error: {response.status_code}"
        except Exception as e:
            ollama_status = f"error: {str(e)}"

        return {
            "session_id": session_id,
            "conversation_info": debug_info,
            "ollama_status": ollama_status,
            "ollama_url": system.config.ollama.base_url,
            "summary_llm_model": system.config.models.llm if system.conversation_manager.summary_llm else "未初始化",
            "timestamp": datetime.now().isoformat()
        }

    # ==================== 调试端点 ====================
    @app.get("/api/debug/conversation/{session_id}")
    async def debug_conversation(session_id: str):
        """调试端点：查看对话详情"""
        conversation = system.conversation_manager.get_or_create_conversation(session_id)
        return {
            "session_id": session_id,
            "message_count": len(conversation.messages),
            "messages": [msg.to_dict() for msg in conversation.messages],
            "summary": conversation.summary,
            "summary_version": conversation.summary_version,
            "last_summary_time": conversation.last_summary_time
        }

    # ==================== WebSocket端点 ====================

    @app.websocket("/api/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket端点"""
        await connection_manager.connect(websocket)

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                message_type = message.get("type", "query")

                if message_type == "get_system_info":
                    # 获取系统信息
                    system_info = system.get_system_info()
                    await websocket.send_json({
                        "type": "system_info",
                        **system_info
                    })

                elif message_type == "get_conversation_info":
                    # 获取对话信息
                    session_id = message.get("session_id", "default")
                    conversation_stats = system.conversation_manager.get_stats(session_id)
                    await websocket.send_json({
                        "type": "conversation_info",
                        "session_id": session_id,
                        **conversation_stats
                    })

                elif message_type == "clear_conversation":
                    # 清空对话历史
                    session_id = message.get("session_id", "default")
                    system.conversation_manager.clear_conversation(session_id)
                    await websocket.send_json({
                        "type": "conversation_cleared",
                        "session_id": session_id,
                        "message": "对话历史已清空"
                    })

                elif message_type == "generate_summary":
                    # 生成对话摘要
                    session_id = message.get("session_id", "default")
                    summary = await system.conversation_manager.generate_summary(session_id)
                    await websocket.send_json({
                        "type": "summary_generated",
                        "session_id": session_id,
                        "summary": summary,
                        "status": "success" if summary else "failed"
                    })

                elif message_type == "query":
                    question = message.get("question", "")
                    session_id = message.get("session_id", "default")
                    stream = message.get("stream", True)

                    if not question:
                        await websocket.send_json({
                            "type": "error",
                            "message": "问题不能为空"
                        })
                        continue

                    try:
                        if stream:
                            # 发送流式开始信号
                            await websocket.send_json({
                                "type": "stream_start",
                                "question": question,
                                "session_id": session_id,
                                "timestamp": datetime.now().isoformat()
                            })

                            # 获取对话上下文
                            conversation_context = system.conversation_manager.get_conversation_context(session_id)

                            # 执行流式查询
                            full_answer = ""
                            sources = []

                            async for chunk in system.stream_query(question, conversation_context, session_id):
                                if chunk.get("type") == "chunk":
                                    # 发送流式块
                                    chunk_content = chunk["content"]
                                    full_answer += chunk_content
                                    await websocket.send_json({
                                        "type": "stream_chunk",
                                        "chunk": chunk_content,
                                        "question": question
                                    })
                                elif chunk.get("type") == "sources":
                                    # 保存来源信息
                                    sources = chunk.get("sources", [])
                                    await websocket.send_json({
                                        "type": "sources_info",
                                        "sources": sources,
                                        "count": len(sources)
                                    })
                                elif chunk.get("type") == "conversation_stats":
                                    # 发送对话统计
                                    full_stats = system.conversation_manager.get_stats(session_id)
                                    await websocket.send_json({
                                        "type": "conversation_stats",
                                        **full_stats
                                    })
                                elif chunk.get("type") == "error":
                                    # 发送错误信息
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": chunk["content"]
                                    })
                                    break

                            # 发送流式结束信号
                            await websocket.send_json({
                                "type": "stream_end",
                                "question": question,
                                "answer": full_answer,
                                "sources": sources,
                                "session_id": session_id,
                                "timestamp": datetime.now().isoformat(),
                                "conversation_stats": system.conversation_manager.get_stats(session_id)
                            })
                        else:
                            # 非流式查询
                            result = await system.query(question, session_id)

                            # 发送结果
                            await websocket.send_json({
                                "type": "result",
                                "question": question,
                                "answer": result.get("answer", ""),
                                "response_type": result.get("type", "direct"),
                                "function_call": result.get("function_call"),
                                "sources": result.get("rag_sources", []),
                                "conversation_stats": result.get("conversation_stats", {}),
                                "session_id": session_id,
                                "timestamp": datetime.now().isoformat()
                            })

                    except Exception as e:
                        logger.error(f"查询处理错误: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"处理失败: {str(e)}"
                        })

                elif message_type == "list_tools":
                    # 列出所有工具
                    tools = system.get_tools_info()
                    await websocket.send_json({
                        "type": "tools_list",
                        "tools": [tool.dict() for tool in tools],
                        "count": len(tools)
                    })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"未知的消息类型: {message_type}"
                    })

        except WebSocketDisconnect:
            connection_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket处理错误: {e}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": f"服务器错误: {str(e)}"
                })
            except:
                pass

    return app


def run_server():
    """运行服务器"""
    app = create_app()

    config = get_config_manager().get_config()

    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="info",
        reload=False  # 生产环境设置为False
    )


if __name__ == "__main__":
    run_server()