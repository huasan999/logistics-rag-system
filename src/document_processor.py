"""
文档处理模块
负责加载、分割和预处理知识库文档
"""
import os
import logging
from typing import List
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from src.config import get_config_manager


logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理器"""

    def __init__(self, config=None):
        if config is None:
            config = get_config_manager().get_config()
        self.config = config

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
            length_function=len,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""]
        )

    def load_documents(self) -> List[Document]:
        """加载文档"""
        kb_config = self.config.knowledge_base
        data_dir = Path(kb_config.data_dir)
        main_file = data_dir / kb_config.main_file

        if not main_file.exists():
            logger.warning(f"知识库文件不存在: {main_file}")
            return []

        try:
            loader = TextLoader(str(main_file), encoding='utf-8')
            documents = loader.load()
            logger.info(f"成功加载知识库文件: {main_file}")
            return documents
        except Exception as e:
            logger.error(f"加载知识库文件失败: {e}")
            return []

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """分割文档"""
        if not documents:
            logger.warning("文档列表为空，无需分割")
            return []

        splits = self.text_splitter.split_documents(documents)
        logger.info(f"文档分割完成: {len(documents)} -> {len(splits)} 个块")

        # 为每个块添加元数据
        for i, split in enumerate(splits):
            split.metadata["chunk_id"] = i
            split.metadata["source"] = split.metadata.get("source", "物流知识库")

        return splits

    def process_knowledge_base(self) -> List[Document]:
        """处理整个知识库"""
        # 加载文档
        raw_documents = self.load_documents()

        if not raw_documents:
            logger.warning("未找到任何文档")
            return []

        # 分割文档
        processed_documents = self.split_documents(raw_documents)

        return processed_documents