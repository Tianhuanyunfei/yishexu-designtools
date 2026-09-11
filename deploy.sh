#!/bin/bash
# 一键部署脚本
# 使用方法: ./deploy.sh

set -e

echo "=========================================="
echo "    羿射旭阻尼器设计工具集 - 部署脚本"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: Python 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 已安装"

# 检查Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误: Node.js 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Node.js 已安装"

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "=========================================="
echo "    1. 构建前端"
echo "=========================================="

cd "$SCRIPT_DIR/web-app"

# 安装前端依赖（如果node_modules不存在）
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 构建生产版本
echo "构建生产版本..."
npm run build

if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 前端构建失败${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} 前端构建完成"

echo ""
echo "=========================================="
echo "    2. 安装后端依赖"
echo "=========================================="

cd "$SCRIPT_DIR/backend"

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "创建Python虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

echo -e "${GREEN}✓${NC} 后端依赖安装完成"

echo ""
echo "=========================================="
echo "    3. 部署完成"
echo "=========================================="
echo ""
echo "启动命令："
echo "  后端: source venv/bin/activate && python app.py"
echo "  或使用run.py"
echo ""
echo -e "${GREEN}部署成功！${NC}"
