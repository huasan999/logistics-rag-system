"""
配置管理模块
"""
import yaml
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ModelConfig(BaseModel):
    """
    模型配置

    Attributes:
        llm (str): 默认使用的语言模型名称，默认为 "qwen2.5:7b"
        embedding (str): 嵌入模型名称，默认为 "nomic-embed-text"
        temperature (float): 采样温度，控制输出随机性，默认为 0.3
        max_tokens (int): 最大生成 token 数量，默认为 1024
    """
    provider: str = "ollama"
    llm: str = "qwen2.5:7b"
    embedding: str = "nomic-embed-text"
    temperature: float = 0.3
    max_tokens: int = 1024


class DeepSeekConfig(BaseModel):
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com/"
    api_key_env: str = "DEEPSEEK_API_KEY"
    timeout: int = 120


class OllamaConfig(BaseModel):
    """
    Ollama 配置

    Attributes:
        base_url (str): Ollama API 的基础 URL，默认为 "http://localhost:11434"
        timeout (int): 请求超时时间（秒），默认为 120 秒
    """
    base_url: str = "http://localhost:11434"
    timeout: int = 120


class VectorStoreConfig(BaseModel):
    """
    向量存储配置

    Attributes:
        collection_name (str): Chroma 数据库中的集合名称，默认为 "logistics_knowledge"
        persist_directory (str): 数据持久化目录路径，默认为 "./chroma_db"
        search_k (int): 查询时返回的最近邻数量，默认为 5
    """
    collection_name: str = "logistics_knowledge"
    persist_directory: str = "./chroma_db"
    search_k: int = 5


class RAGConfig(BaseModel):
    """
    RAG 相关配置

    Attributes:
        enable_function_call (bool): 是否启用函数调用功能，默认为 True
        function_call_mode (str): 函数调用模式，可选值："auto", "always", "never"，默认为 "auto"
    """
    enable_function_call: bool = True
    function_call_mode: str = "auto"  # auto, always, never


class KnowledgeBaseConfig(BaseModel):
    """
    知识库相关配置

    Attributes:
        data_dir (str): 存放知识数据的目录路径，默认为 "./data"
        main_file (str): 主要的知识文本文件名，默认为 "logistics_knowledge.txt"
    """
    data_dir: str = "./data"
    main_file: str = "logistics_knowledge.txt"


class ServerConfig(BaseModel):
    """
    服务器运行配置

    Attributes:
        host (str): 服务监听地址，默认为 "0.0.0.0"
        port (int): 服务监听端口，默认为 8000
        enable_websocket (bool): 是否启用 WebSocket 支持，默认为 True
    """
    host: str = "0.0.0.0"
    port: int = 8000
    enable_websocket: bool = True


class ToolsConfig(BaseModel):
    """
    工具插件配置

    Attributes:
        enabled_categories (list): 启用的工具类别列表，默认包括 calculator、logistics 和 web 类别
        disabled_tools (list): 被禁用的具体工具列表，默认为空列表
    """
    enabled_categories: list = ["calculator", "logistics", "web"]
    disabled_tools: list = Field(default_factory=list)


class SystemConfig(BaseModel):
    """
    系统基本信息配置

    Attributes:
        name (str): 系统名称，默认为 "物流智能问答系统"
        version (str): 系统版本号，默认为 "2.0.0"
        mode (str): 运行模式，支持 basic 或 enhanced，默认为 "enhanced"
    """
    name: str = "物流智能问答系统"
    version: str = "2.0.0"
    mode: str = "enhanced"  # basic, enhanced


class LoggingConfig(BaseModel):
    """
    日志记录配置

    Attributes:
        level (str): 日志级别，默认为 "INFO"
        file (str): 日志输出文件路径，默认为 "logistics_system.log"
    """
    level: str = "INFO"
    file: str = "logistics_system.log"


class ConversationConfig(BaseModel):
    """
    对话相关配置

    Attributes:
        max_messages (int): 最大消息数限制，默认为50
        summary_min_messages (int): 生成摘要所需的最小消息数，默认为10
        summary_interval (int): 生成摘要的间隔消息数，默认为5
        enable_auto_summary (bool): 是否启用自动摘要生成，默认为True
    """
    max_messages: int = 50
    summary_min_messages: int = 8
    summary_interval: int = 5
    enable_auto_summary: bool = True

class AppConfig(BaseModel):
    """
    应用整体配置结构定义

    Attributes:
        system (SystemConfig): 系统基本配置信息
        models (ModelConfig): 使用的语言模型与嵌入模型配置
        ollama (OllamaConfig): Ollama 接口访问配置
        vector_store (VectorStoreConfig): 向量数据库相关设置
        rag (RAGConfig): RAG 功能开关及行为控制选项
        knowledge_base (KnowledgeBaseConfig): 知识库文件位置等设定
        server (ServerConfig): Web 服务启动参数
        tools (ToolsConfig): 可用工具及其启用状态
        logging (LoggingConfig): 日志记录规则
    """
    system: SystemConfig = Field(default_factory=SystemConfig)
    models: ModelConfig = Field(default_factory=ModelConfig)
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    knowledge_base: KnowledgeBaseConfig = Field(default_factory=KnowledgeBaseConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)  # 新增


class ConfigManager:
    """
    配置管理器，用于加载、保存和更新应用程序配置

    Attributes:
        config_path (Optional[str]): 配置文件路径
        config (AppConfig): 当前生效的应用程序配置对象
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_path (Optional[str]): 自定义配置文件路径。如果未提供则默认使用 "config.yaml"
        """
        self.config_path = config_path or "config.yaml"
        self.config = self.load_config()

    def load_config(self) -> AppConfig:
        """
        加载并解析 YAML 格式的配置文件

        Returns:
            AppConfig: 解析后的配置对象；若加载失败或文件不存在，则返回默认配置
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                return AppConfig(**config_data)
            except Exception as e:
                print(f"加载配置文件失败，使用默认配置: {e}")

        # 返回默认配置
        return AppConfig()

    def get_config(self) -> AppConfig:
        """
        获取当前已加载的配置对象

        Returns:
            AppConfig: 当前应用配置对象
        """
        return self.config

    def save_config(self, config: Optional[AppConfig] = None):
        """
        将配置对象序列化后写入到配置文件中

        Args:
            config (Optional[AppConfig]): 待保存的配置对象。如未指定则使用当前实例中的配置
        """
        if config is None:
            config = self.config

        with open(self.config_path, 'w', encoding='utf-8') as f:
            config_dict = config.model_dump()
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True, indent=2)

    def update_config(self, updates: Dict[str, Any]):
        """
        更新现有配置，并将更改同步至磁盘上的配置文件

        Args:
            updates (Dict[str, Any]): 包含需要更新字段的新值字典
        """
        config_dict = self.config.model_dump()

        # 递归更新配置
        self._update_dict(config_dict, updates)

        # 重新创建配置对象
        self.config = AppConfig(**config_dict)
        self.save_config()

    def _update_dict(self, target: Dict[str, Any], updates: Dict[str, Any]):
        """
        递归地合并两个字典结构以实现深层更新

        Args:
            target (Dict[str, Any]): 目标字典，将被修改
            updates (Dict[str, Any]): 来源字典，包含新的键值对
        """
        for key, value in updates.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._update_dict(target[key], value)
            else:
                target[key] = value


# 全局配置管理器实例
_config_manager = None

def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """
    获取全局唯一的配置管理器实例

    Args:
        config_path (Optional[str]): 若首次初始化，可以传入自定义配置文件路径

    Returns:
        ConfigManager: 配置管理器单例对象
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager
