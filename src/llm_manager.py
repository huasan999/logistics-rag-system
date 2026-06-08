"""
LLM管理器
统一管理LLM和嵌入模型
"""
import logging
import os
from typing import Optional, Dict, Any

import httpx
from langchain_community.llms import Ollama
from langchain_ollama import OllamaEmbeddings
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableLambda

from src.config import AppConfig, get_config_manager


logger = logging.getLogger(__name__)


class LLMManager:
    """LLM管理器"""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or get_config_manager().get_config()
        self.llm = None
        self.embeddings = None
        self._initialize_llm()
        self._initialize_embeddings()

    def _initialize_llm(self):
        """初始化LLM"""
        try:
            provider = self.config.models.provider.lower()
            if provider == "deepseek":
                self._initialize_deepseek_llm()
            else:
                self.llm = Ollama(
                    model=self.config.models.llm,
                    base_url=self.config.ollama.base_url,
                    temperature=self.config.models.temperature,
                    num_predict=self.config.models.max_tokens,
                    timeout=self.config.ollama.timeout
                )
                logger.info(f"LLM初始化成功: {self.config.models.llm}")
        except Exception as e:
            logger.error(f"LLM初始化失败: {e}")
            raise

    def _initialize_deepseek_llm(self):
        api_key = os.getenv(self.config.deepseek.api_key_env)
        if not api_key:
            raise ValueError(f"未设置环境变量: {self.config.deepseek.api_key_env}")

        self.llm = RunnableLambda(self._invoke_deepseek, afunc=self._ainvoke_deepseek)
        logger.info(f"DeepSeek LLM初始化成功: {self.config.deepseek.model}")

    def _build_deepseek_messages(self, input_data):
        if hasattr(input_data, "to_messages"):
            raw_messages = input_data.to_messages()
        elif isinstance(input_data, list):
            raw_messages = input_data
        elif isinstance(input_data, str):
            return [{"role": "user", "content": input_data}]
        else:
            return [{"role": "user", "content": str(input_data)}]

        messages = []
        for message in raw_messages:
            if isinstance(message, BaseMessage):
                role = {
                    "human": "user",
                    "ai": "assistant",
                    "system": "system"
                }.get(message.type, "user")
                messages.append({"role": role, "content": message.content})
            elif isinstance(message, dict):
                messages.append({
                    "role": message.get("role", "user"),
                    "content": message.get("content", "")
                })
            else:
                messages.append({"role": "user", "content": str(message)})

        return messages

    def _deepseek_payload(self, input_data):
        return {
            "model": self.config.deepseek.model,
            "messages": self._build_deepseek_messages(input_data),
            "temperature": self.config.models.temperature,
            "max_tokens": self.config.models.max_tokens
        }

    def _deepseek_headers(self):
        return {
            "Authorization": f"Bearer {os.getenv(self.config.deepseek.api_key_env)}",
            "Content-Type": "application/json"
        }

    def _deepseek_url(self):
        return f"{self.config.deepseek.base_url.rstrip('/')}/chat/completions"

    def _extract_deepseek_content(self, response_data):
        return response_data["choices"][0]["message"]["content"]

    def _invoke_deepseek(self, input_data):
        with httpx.Client(timeout=self.config.deepseek.timeout) as client:
            response = client.post(
                self._deepseek_url(),
                headers=self._deepseek_headers(),
                json=self._deepseek_payload(input_data)
            )
            response.raise_for_status()
            return self._extract_deepseek_content(response.json())

    async def _ainvoke_deepseek(self, input_data):
        async with httpx.AsyncClient(timeout=self.config.deepseek.timeout) as client:
            response = await client.post(
                self._deepseek_url(),
                headers=self._deepseek_headers(),
                json=self._deepseek_payload(input_data)
            )
            response.raise_for_status()
            return self._extract_deepseek_content(response.json())

    def _initialize_embeddings(self):
        """初始化嵌入模型"""
        try:
            self.embeddings = OllamaEmbeddings(
                model=self.config.models.embedding,
                base_url=self.config.ollama.base_url,
                # timeout=self.config.ollama.timeout
            )
            logger.info(f"嵌入模型初始化成功: {self.config.models.embedding}")
        except Exception as e:
            logger.error(f"嵌入模型初始化失败: {e}")
            raise

    def get_llm(self) -> Ollama:
        """获取LLM实例"""
        if self.llm is None:
            self._initialize_llm()
        return self.llm

    def get_embeddings(self) -> OllamaEmbeddings:
        """获取嵌入模型"""
        if self.embeddings is None:
            self._initialize_embeddings()
        return self.embeddings

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": self.config.models.provider,
            "llm_model": self.config.models.llm,
            "deepseek_model": self.config.deepseek.model,
            "embedding_model": self.config.models.embedding,
            "temperature": self.config.models.temperature,
            "max_tokens": self.config.models.max_tokens,
            "ollama_url": self.config.ollama.base_url
        }