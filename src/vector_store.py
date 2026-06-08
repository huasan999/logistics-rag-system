"""
向量存储管理器
统一管理向量数据库
"""
import os
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.llm_manager import LLMManager
from src.config import get_config_manager


logger = logging.getLogger(__name__)


class VectorStoreManager:
    """向量存储管理器"""

    def __init__(self, config=None, embeddings=None):
        if config is None:
            config = get_config_manager().get_config()
        self.config = config.vector_store
        self.embeddings = embeddings or LLMManager().get_embeddings()
        self.vectorstore = None

    def exists(self) -> bool:
        """检查向量存储是否存在"""
        persist_dir = Path(self.config.persist_directory)
        return persist_dir.exists() and any(persist_dir.iterdir())

    def create_vectorstore(self, documents: List[Document]) -> Chroma:
        """创建向量存储"""
        if not self.embeddings:
            raise ValueError("嵌入模型未设置")

        try:
            # 确保存储目录存在
            persist_dir = Path(self.config.persist_directory)
            persist_dir.mkdir(parents=True, exist_ok=True)

            # 创建向量存储
            self.vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=str(persist_dir),
                collection_name=self.config.collection_name
            )

            logger.info(f"向量存储创建成功: {len(documents)} 个文档")
            return self.vectorstore

        except Exception as e:
            logger.error(f"向量存储创建失败: {e}")
            raise

    def load_vectorstore(self) -> Optional[Chroma]:
        """加载现有向量存储"""
        if not self.embeddings:
            raise ValueError("嵌入模型未设置")

        persist_dir = Path(self.config.persist_directory)

        if not self.exists():
            logger.warning(f"向量存储目录不存在或为空: {persist_dir}")
            return None

        try:
            self.vectorstore = Chroma(
                persist_directory=str(persist_dir),
                embedding_function=self.embeddings,
                collection_name=self.config.collection_name
            )

            # 检查集合是否存在
            count = self.vectorstore._collection.count()
            logger.info(f"向量存储加载成功: {count} 个文档")

            return self.vectorstore

        except Exception as e:
            logger.error(f"向量存储加载失败: {e}")
            return None

    def get_or_create_vectorstore(self, documents: Optional[List[Document]] = None) -> Chroma:
        """获取或创建向量存储"""
        # 尝试加载现有存储
        vectorstore = self.load_vectorstore()

        if vectorstore is None and documents is not None:
            # 创建新存储
            vectorstore = self.create_vectorstore(documents)

        self.vectorstore = vectorstore
        return vectorstore

    def get_retriever(self, search_k: Optional[int] = None):
        """获取检索器"""
        if self.vectorstore is None:
            raise ValueError("向量存储未初始化")

        if search_k is None:
            search_k = self.config.search_k

        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": search_k}
        )

    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        if self.vectorstore is None:
            return {"error": "向量存储未初始化"}

        try:
            collection = self.vectorstore._collection
            count = collection.count()

            return {
                "collection_name": self.config.collection_name,
                "document_count": count,
                "persist_directory": self.config.persist_directory
            }
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {"error": str(e)}