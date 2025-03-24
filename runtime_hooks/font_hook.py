
import os
import sys
import traceback
import PyQt5

def setup_fonts():
    try:
        # 获取可执行文件所在的目录
        if getattr(sys, 'frozen', False):
            # 打包后的可执行文件路径
            base_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境中脚本路径
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 检查并添加字体目录
        fonts_dir = os.path.join(base_dir, 'fonts')
        if os.path.exists(fonts_dir):
            print(f"找到字体目录: {fonts_dir}")
            # 确保系统可以找到字体
            os.environ['QT_QPA_FONTDIR'] = fonts_dir
        else:
            print(f"警告: 字体目录不存在: {fonts_dir}")
    except Exception as e:
        print(f"设置字体路径时出错: {e}")
        traceback.print_exc()

setup_fonts()
