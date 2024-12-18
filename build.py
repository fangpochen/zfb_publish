import PyInstaller.__main__
import os

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

PyInstaller.__main__.run([
    'main.py',  # 主程序文件
    '--name=支付宝视频发布工具',  # 生成的exe名称
    '--windowed',  # 使用 GUI 模式
    '--icon=ui/icon.ico',  # 程序图标（如果有的话）
    '--add-data=ui/*;ui/',  # 添加 UI 资源文件
    '--add-data=default_cover.jpg;.',  # 添加默认封面图
    '--noconfirm',  # 覆盖输出目录
    '--clean',  # 清理临时文件
    '--onedir',  # 生成单文件夹
    # '--onefile',  # 如果想生成单文件则使用这个选项
    '--hidden-import=cv2',  # 添加隐式导入
    '--hidden-import=numpy',
    '--hidden-import=pandas',
    '--hidden-import=sqlite3',
    '--hidden-import=requests',
    '--hidden-import=concurrent.futures',
    '--hidden-import=PIL',
    '--hidden-import=PyQt5',
])