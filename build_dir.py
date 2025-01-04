
import PyInstaller.__main__
import os
import shutil

# 确保logo.ico存在
if not os.path.exists('logo.ico'):
    raise FileNotFoundError("logo.ico not found!")

# 创建临时目录用于存放需要打包的文件
os.makedirs('dist/internal', exist_ok=True)

# 复制需要的模块到dist/internal目录
module_files = [
    'zfb.py',
    'key_verification.py',
    'db.py',
    'ui/ui.py',
    'default_cover.jpg',
    'logo.ico'
]

for file in module_files:
    if os.path.exists(file):
        if '/' in file:
            # 创建子目录
            os.makedirs(os.path.join('dist/internal', os.path.dirname(file)), exist_ok=True)
        shutil.copy2(file, os.path.join('dist/internal', file))

# 打包配置
PyInstaller.__main__.run([
    'app.py',                     # 主程序文件
    '--name=视频批量上传',         # 生成的exe名称
    '--windowed',                 # 使用GUI模式
    '--icon=logo.ico',           # 指定图标
    '--add-data=logo.ico;.',     # 将图标文件打包进exe
    '--onefile',                  # 打包成单个文件
    '--clean',                   # 清理临时文件
    '--noconfirm',              # 不确认覆盖
    '--hidden-import=PIL',       # 添加PIL依赖
    '--hidden-import=PIL._imaging',  # 添加PIL子模块
    '--hidden-import=cv2',       # 添加OpenCV依赖
    '--hidden-import=numpy',     # 添加numpy依赖
    '--collect-all=cv2',        # 收集所有cv2相关文件
    '--collect-all=numpy',      # 收集所有numpy相关文件
    '--runtime-tmpdir=.',       # 设置运行时临时目录
    '--add-data=dist/internal;internal'  # 添加模块目录
])

# 清理临时目录
shutil.rmtree('dist/internal') 