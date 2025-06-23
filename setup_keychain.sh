#!/bin/bash

# macOS Keychain API Key 管理脚本

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔐 macOS Keychain API Key 管理"
echo "==============================="

# 服务名称
SERVICE_NAME="translation-app"

# 存储 Claude API Key
store_claude_key() {
    echo -n "请输入 Claude API Key: "
    read -s CLAUDE_KEY
    echo
    
    security add-generic-password \
        -a "CLAUDE_API_KEY" \
        -s "$SERVICE_NAME" \
        -w "$CLAUDE_KEY" \
        -T "" \
        -U
    
    echo -e "${GREEN}✅ Claude API Key 已安全存储到 Keychain${NC}"
}

# 获取 Claude API Key
get_claude_key() {
    CLAUDE_KEY=$(security find-generic-password \
        -a "CLAUDE_API_KEY" \
        -s "$SERVICE_NAME" \
        -w 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 找到 Claude API Key${NC}"
        echo "export CLAUDE_API_KEY='$CLAUDE_KEY'"
    else
        echo -e "${RED}❌ 未找到 Claude API Key${NC}"
    fi
}

# 删除 Claude API Key
delete_claude_key() {
    security delete-generic-password \
        -a "CLAUDE_API_KEY" \
        -s "$SERVICE_NAME" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Claude API Key 已从 Keychain 删除${NC}"
    else
        echo -e "${YELLOW}⚠️  未找到要删除的 Key${NC}"
    fi
}

# 设置环境变量（用于当前 shell）
setup_env() {
    CLAUDE_KEY=$(security find-generic-password \
        -a "CLAUDE_API_KEY" \
        -s "$SERVICE_NAME" \
        -w 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        export CLAUDE_API_KEY="$CLAUDE_KEY"
        echo -e "${GREEN}✅ 环境变量已设置${NC}"
    else
        echo -e "${RED}❌ 请先存储 API Key${NC}"
    fi
}

# 显示菜单
show_menu() {
    echo
    echo "选择操作："
    echo "1) 存储 Claude API Key"
    echo "2) 获取 Claude API Key"
    echo "3) 删除 Claude API Key"
    echo "4) 设置环境变量"
    echo "5) 退出"
    echo
    echo -n "请选择 (1-5): "
}

# 主循环
while true; do
    show_menu
    read choice
    
    case $choice in
        1) store_claude_key ;;
        2) get_claude_key ;;
        3) delete_claude_key ;;
        4) setup_env ;;
        5) echo "再见！"; exit 0 ;;
        *) echo -e "${RED}无效选择${NC}" ;;
    esac
done