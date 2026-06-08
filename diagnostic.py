# diagnostic.py
import asyncio
import logging
from src.conversation_manager import get_conversation_manager
from src.config import get_config_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def diagnose_conversation_issue():
    """诊断对话管理问题"""
    config = get_config_manager().get_config()
    manager = get_conversation_manager(config)

    # 检查配置
    logger.info("=== 配置检查 ===")
    logger.info(f"配置对象: {config}")
    logger.info(f"对话配置: {config.conversation}")
    logger.info(f"最小摘要消息数: {config.conversation.summary_min_messages}")
    logger.info(f"摘要间隔: {config.conversation.summary_interval}")

    # 检查所有会话
    logger.info("\n=== 当前所有会话 ===")
    for session_id, conversation in manager.conversations.items():
        logger.info(f"会话 {session_id}:")
        logger.info(f"  消息数量: {len(conversation.messages)}")
        logger.info(f"  是否有摘要: {bool(conversation.summary)}")
        logger.info(f"  摘要版本: {conversation.summary_version}")

        # 显示前3条消息
        for i, msg in enumerate(conversation.messages[:3]):
            logger.info(f"  消息{i + 1}: {msg.role} - {msg.content[:50]}...")

    # 检查LLM管理器
    logger.info("\n=== LLM管理器检查 ===")
    try:
        from src.llm_manager import LLMManager
        llm_manager = LLMManager(config)
        logger.info(f"LLM模型: {config.models.llm}")
        logger.info(f"Ollama URL: {config.ollama.base_url}")
    except Exception as e:
        logger.error(f"LLM管理器检查失败: {e}")


if __name__ == "__main__":
    asyncio.run(diagnose_conversation_issue())