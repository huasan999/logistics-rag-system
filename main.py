"""
物流RAG系统主程序入口
"""
import os
import sys
import logging
import argparse
import asyncio
from pathlib import Path
from datetime import datetime

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config_manager
from src.web_api import run_server


def setup_logging(config):
    """
    配置日志记录器

    Args:
        config: 系统配置对象，包含日志级别和日志文件路径

    Returns:
        logging.Logger: 配置好的日志记录器实例
    """
    logging.basicConfig(
        level=getattr(logging, config.logging.level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.logging.file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def test_system():
    """
    测试系统核心功能是否正常工作

    Returns:
        bool: 测试是否成功
    """
    import asyncio

    logger = logging.getLogger(__name__)

    async def run_tests():
        logger.info("开始系统测试...")

        try:
            # 1. 测试配置加载
            config = get_config_manager().get_config()
            logger.info(f"配置加载成功: {config.system.name} v{config.system.version}")

            # 2. 测试系统初始化
            from src.web_api import LogisticsRAGSystem
            system = LogisticsRAGSystem()

            # 3. 测试系统信息获取
            system_info = system.get_system_info()
            logger.info(f"系统信息: {system_info}")

            # 4. 测试查询功能
            if system.rag_pipeline:
                test_result = await system.query("什么是物流？")
                logger.info(f"查询测试成功: {test_result.get('answer', '')[:100]}...")

                if test_result.get('rag_sources'):
                    logger.info(f"找到 {len(test_result['rag_sources'])} 个相关文档")

            logger.info("系统测试完成")
            return True

        except Exception as e:
            logger.error(f"系统测试失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    return asyncio.run(run_tests())


async def run_cli_mode(config):
    """
    运行命令行交互模式，提供用户与系统的文本对话接口

    Args:
        config: 系统配置对象，用于初始化各个组件
    """
    from src.llm_manager import LLMManager
    from src.vector_store import VectorStoreManager
    from src.document_processor import DocumentProcessor
    from src.rag_pipeline import create_rag_pipeline
    from src.tool_registry import get_tool_registry
    from src.function_caller import FunctionCaller, FunctionCallMode
    from src.enhanced_rag import create_enhanced_rag_pipeline

    logger = logging.getLogger(__name__)

    try:
        # 初始化系统组件
        logger.info("正在初始化系统...")

        # 1. 初始化LLM管理器
        llm_manager = LLMManager(config)

        # 2. 初始化向量存储
        vector_manager = VectorStoreManager(config, llm_manager.get_embeddings())

        # 3. 处理知识库
        processor = DocumentProcessor(config)
        documents = processor.process_knowledge_base()

        if documents:
            vector_manager.get_or_create_vectorstore(documents)
            logger.info(f"知识库加载完成: {len(documents)} 个文档块")

        # 4. 创建管道
        if config.rag.enable_function_call and config.system.mode == "enhanced":
            tool_registry = get_tool_registry(config.tools)

            # 映射配置模式到函数调用模式
            mode_map = {
                "auto": FunctionCallMode.AUTO,
                "always": FunctionCallMode.ALWAYS,
                "never": FunctionCallMode.NEVER
            }
            mode = mode_map.get(config.rag.function_call_mode, FunctionCallMode.AUTO)

            function_caller = FunctionCaller(
                llm=llm_manager.get_llm(),
                tool_registry=tool_registry,
                mode=mode
            )

            rag_pipeline = create_rag_pipeline(llm_manager, vector_manager)
            pipeline = create_enhanced_rag_pipeline(rag_pipeline, function_caller, mode=mode)
            logger.info(f"增强RAG管道已启用 (模式: {mode.value})")
        else:
            pipeline = create_rag_pipeline(llm_manager, vector_manager)
            logger.info("基础RAG管道已启用")

        # 5. 开始交互
        print("\n" + "="*60)
        print(f"🚚 物流智能问答系统 v{config.system.version}")
        print("="*60)
        print(f"模式: {config.system.mode}")
        print(f"模型: {config.models.llm}")
        print(f"温度: {config.models.temperature}")
        print("="*60)
        print("\n输入 'quit' 或 'exit' 退出程序")
        print("输入 'clear' 清屏")
        print("输入 'help' 查看帮助")
        print("-"*60)

        while True:
            try:
                # 获取用户输入
                question = input("\n您: ").strip()

                if not question:
                    continue

                # 处理特殊命令
                if question.lower() in ['quit', 'exit', 'q']:
                    print("👋 感谢使用，再见！")
                    break
                elif question.lower() == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    continue
                elif question.lower() == 'help':
                    print("\n📚 使用帮助:")
                    print("  1. 直接提问物流相关问题")
                    print("  2. 示例问题:")
                    print("     - 什么是FOB？")
                    print("     - 计算从上海到北京运输500公斤货物的成本")
                    print("     - 将100公斤转换为磅")
                    print("     - 什么是第三方物流？")
                    print("  3. 特殊命令:")
                    print("     - quit/exit: 退出程序")
                    print("     - clear: 清屏")
                    print("     - help: 显示帮助")
                    continue

                # 显示正在思考
                print("🤔 正在思考...", end="\r")

                # 执行查询
                result = await pipeline.query(question)

                # 清除"正在思考"提示
                print(" " * 30, end="\r")

                # 显示回答
                if result.get("status") == "success":
                    print(f"\n💡 助手:", end=" ")

                    # 如果是流式输出
                    if hasattr(pipeline, 'stream_query') and config.models.temperature > 0:
                        async for chunk in pipeline.stream_query(question):
                            print(chunk, end="", flush=True)
                        print()
                    else:
                        print(result.get("answer", ""))

                    # 显示来源信息
                    if result.get("source_count", 0) > 0:
                        print(f"\n📚 参考了 {result.get('source_count')} 个知识库文档")

                    # 显示函数调用信息
                    if result.get("function_call"):
                        print(f"⚙️  调用了工具: {result.get('function_call', {}).get('name')}")

                else:
                    print(f"❌ 错误: {result.get('error', '未知错误')}")

            except KeyboardInterrupt:
                print("\n\n⏹️  已取消当前查询")
                continue
            except Exception as e:
                print(f"❌ 处理失败: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"系统初始化失败: {e}")
        print(f"❌ 系统启动失败: {e}")


def main():
    """
    主函数，解析命令行参数并根据指定模式启动系统
    """
    parser = argparse.ArgumentParser(description="物流RAG问答系统")
    parser.add_argument("--mode", choices=["api", "web", "cli", "test"], default="web",
                       help="运行模式: api(API服务), web(Web界面), cli(命令行), test(测试)")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--host", help="服务器主机")
    parser.add_argument("--port", type=int, help="服务器端口")
    parser.add_argument("--init-kb", action="store_true", help="初始化知识库")
    # parser.add_argument("--test", action="store_true", help="运行测试")

    args = parser.parse_args()

    # 加载配置
    config_manager = get_config_manager(args.config)
    config = config_manager.get_config()

    # 覆盖配置
    if args.host:
        config.server.host = args.host
    if args.port:
        config.server.port = args.port

    # 设置日志
    logger = setup_logging(config)

    logger.info(f"========================================")
    logger.info(f"  物流RAG问答系统 v{config.system.version}")
    logger.info(f"========================================")
    logger.info(f"运行模式: {args.mode}")
    logger.info(f"LLM模型: {config.models.llm}")
    logger.info(f"嵌入模型: {config.models.embedding}")
    logger.info(f"函数调用: {'启用' if config.rag.enable_function_call else '禁用'}")
    logger.info(f"系统模式: {config.system.mode}")

    # 处理初始化知识库
    if args.init_kb:
        logger.info("初始化知识库...")
        from src.document_processor import DocumentProcessor
        from src.vector_store import VectorStoreManager
        from src.llm_manager import LLMManager

        processor = DocumentProcessor(config)
        documents = processor.process_knowledge_base()

        if documents:
            llm_manager = LLMManager(config)
            vector_manager = VectorStoreManager(config, llm_manager.get_embeddings())
            vector_manager.create_vectorstore(documents)
            logger.info(f"知识库初始化完成: {len(documents)} 个文档块")
        return

    # 运行测试
    if args.test:
        success = test_system()
        sys.exit(0 if success else 1)

    # 根据模式运行
    if args.mode == "api":
        logger.info(f"启动API服务: http://{config.server.host}:{config.server.port}")
        run_server()

    elif args.mode == "web":
        logger.info(f"启动Web界面: http://{config.server.host}:{config.server.port}")

        # 设置默认访问页面
        from src.web_api import create_app
        import uvicorn

        app = create_app()
        uvicorn.run(
            app,
            host=config.server.host,
            port=config.server.port,
            log_level="info"
        )

    elif args.mode == "cli":
        logger.info("启动命令行模式...")
        asyncio.run(run_cli_mode(config))

    else:
        logger.error(f"未知的运行模式: {args.mode}")


if __name__ == "__main__":
    main()
