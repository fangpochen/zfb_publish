import PyInstaller.__main__
import os

# 确保logo.ico存在
if not os.path.exists('logo.ico'):
    raise FileNotFoundError("logo.ico not found!")

PyInstaller.__main__.run([
    'main.py',                     # 主程序文件
    '--name=视频批量上传',         # 生成的exe名称
    '--windowed',                  # 使用GUI模式
    '--icon=logo.ico',            # 指定图标
    '--add-data=logo.ico;.',      # 将图标文件打包进exe
    '--onefile',                  # 打包成单个文件
    '--clean',                    # 清理临时文件
    '--noconfirm',               # 不确认覆盖
]) 