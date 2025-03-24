#!/bin/bash

echo "========================="
echo " 支付宝上传和分析工具打包"
echo "========================="
echo ""

# 检查Python是否存在
if ! command -v python3 &> /dev/null; then
    echo "错误: 系统未安装Python或Python未添加到PATH"
    echo "请安装Python 3.7或更高版本"
    exit 1
fi

# 检查是否有项目必需文件
if [ ! -f "main.py" ] && [ ! -f "app.py" ]; then
    echo "警告: 未找到main.py或app.py入口文件"
    echo "脚本将尝试自动检测合适的入口文件"
fi

# 显示提示信息
echo "打包前准备..."
echo "- 将自动安装所需依赖"
echo "- 将自动检测适合的入口文件"
echo "- 将自动包含fonts目录下的字体文件"
echo "- 将自动包含项目所需的所有依赖"
echo ""
echo "打包可能需要几分钟时间，请耐心等待..."
echo ""

# 执行打包脚本
echo "开始执行打包脚本..."
python3 build_dir.py

if [ $? -ne 0 ]; then
    echo "打包失败! 请查看错误信息。"
    echo "如果遇到权限问题，请尝试使用sudo运行此脚本。"
else
    echo "打包成功! 可执行文件位于dist目录和当前目录。"
    echo "文件名为: 支付宝上传和分析工具"
fi

read -p "按Enter键继续..." 