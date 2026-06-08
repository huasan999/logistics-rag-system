#!/bin/bash

# ========================================
# 物流RAG系统启动脚本
# ========================================

set -e

echo "========================================"
echo "  物流行业RAG问答系统启动脚本"
echo "========================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 未安装"
        return 1
    fi
    return 0
}

# 检查Python环境
setup_python_env() {
    log_info "设置Python环境..."

    if [ ! -d "venv" ]; then
        log_info "创建Python虚拟环境..."
        python3 -m venv venv
    fi

    log_info "激活虚拟环境..."
    source venv/bin/activate

    log_info "安装Python依赖..."
    pip install -r requirements.txt

    log_success "Python环境设置完成"
}

# 检查Ollama服务
setup_ollama() {
    log_info "检查Ollama服务..."

    # 检查Ollama是否在运行
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_warning "Ollama服务未运行，尝试启动..."

        # 检查是否已安装Ollama
        if ! check_command "ollama"; then
            log_info "安装Ollama..."
            if [[ "$OSTYPE" == "linux-gnu"* ]]; then
                curl -fsSL https://ollama.com/install.sh | sh
            elif [[ "$OSTYPE" == "darwin"* ]]; then
                /bin/bash -c "$(curl -fsSL https://ollama.com/install.sh)"
            else
                log_error "不支持的操作系统: $OSTYPE"
                exit 1
            fi
        fi

        # 启动Ollama服务
        log_info "启动Ollama服务..."
        nohup ollama serve > ollama.log 2>&1 &
        OLLAMA_PID=$!
        echo $OLLAMA_PID > ollama.pid

        # 等待Ollama启动
        log_info "等待Ollama服务启动..."
        sleep 10

        # 检查是否启动成功
        if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            log_error "Ollama服务启动失败"
            exit 1
        fi
    else
        log_success "Ollama服务正在运行"
    fi

    # 下载模型
    log_info "检查模型..."

    # 检查Qwen模型
    if ! ollama list | grep -q "qwen2.5:7b"; then
        log_info "下载Qwen2.5:7B模型..."
        ollama pull qwen2.5:7b
    fi

    # 检查嵌入模型
    if ! ollama list | grep -q "nomic-embed-text"; then
        log_info "下载nomic-embed-text嵌入模型..."
        ollama pull nomic-embed-text
    fi

    log_success "模型检查完成"
}

# 初始化知识库
init_knowledge_base() {
    log_info "初始化知识库..."

    # 创建目录
    mkdir -p data
    mkdir -p chroma_db
    mkdir -p logs

    # 检查知识库文件
    if [ ! -f "data/logistics_knowledge.txt" ]; then
        log_warning "未找到知识库文件，创建示例文件..."
        cat > data/logistics_knowledge.txt << 'EOF'
# 物流基础知识

## 一、基本概念
物流是指物品从供应地向接收地的实体流动过程，包括运输、储存、装卸、搬运、包装、流通加工、配送和信息处理等基本功能。

## 二、运输方式
1. 公路运输：灵活性强，适合中短途运输
2. 铁路运输：运量大，适合长途大宗货物
3. 航空运输：速度快，适合高价值货物
4. 水路运输：成本低，适合大宗货物

## 三、仓储管理
- 仓库布局设计
- 库存管理方法
- 货位管理系统
- 仓储作业流程

## 四、物流单证
1. 运单（Waybill）
2. 装箱单（Packing List）
3. 提单（Bill of Lading）
4. 商业发票（Commercial Invoice）

## 五、物流成本
1. 运输成本
2. 仓储成本
3. 管理成本
4. 库存持有成本

## 六、第三方物流（3PL）
提供运输、仓储、配送等物流服务的专业公司。
EOF
        log_info "示例知识库文件已创建: data/logistics_knowledge.txt"
    fi

    log_success "知识库初始化完成"
}

# 启动系统
start_system() {
    log_info "启动物流RAG系统..."

    # 获取运行模式
    MODE=${1:-"api"}

    case $MODE in
        "api")
            log_info "启动API服务模式..."
            python main.py --mode api
            ;;
        "web")
            log_info "启动Web界面模式..."
            python main.py --mode web
            ;;
        "cli")
            log_info "启动命令行模式..."
            python main.py --mode cli
            ;;
        "test")
            log_info "启动测试模式..."
            python main.py --mode test
            ;;
        *)
            log_error "未知的运行模式: $MODE"
            echo "可用模式: api, web, cli, test"
            exit 1
            ;;
    esac
}

# 清理函数
cleanup() {
    log_info "执行清理..."

    # 停止Ollama服务
    if [ -f "ollama.pid" ]; then
        OLLAMA_PID=$(cat ollama.pid)
        if kill -0 $OLLAMA_PID 2>/dev/null; then
            log_info "停止Ollama服务..."
            kill $OLLAMA_PID
            rm ollama.pid
        fi
    fi

    log_success "清理完成"
}

# 主函数
main() {
    # 设置信号处理
    trap cleanup EXIT INT TERM

    # 检查参数
    if [ $# -gt 0 ]; then
        MODE=$1
    else
        echo "请选择运行模式:"
        echo "  1) API服务模式"
        echo "  2) Web界面模式"
        echo "  3) 命令行模式"
        echo "  4) 测试模式"
        read -p "请输入选择 (1-4): " choice

        case $choice in
            1) MODE="api" ;;
            2) MODE="web" ;;
            3) MODE="cli" ;;
            4) MODE="test" ;;
            *)
                log_error "无效选择"
                exit 1
                ;;
        esac
    fi

    # 执行步骤
    setup_python_env
    setup_ollama
    init_knowledge_base

    log_info "运行模式: $MODE"
    log_info "系统将在 http://localhost:8000 启动"
    log_info "按 Ctrl+C 停止服务"
    echo ""

    start_system $MODE
}

# 运行主函数
main "$@"