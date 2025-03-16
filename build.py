import PyInstaller.__main__
import os
import sys
import shutil
from pathlib import Path

# 确保logo.ico存在
if not os.path.exists('logo.ico'):
    raise FileNotFoundError("logo.ico not found!")

# 创建钩子目录
hooks_dir = Path('hooks')
hooks_dir.mkdir(exist_ok=True)

# 创建自定义钩子文件来处理jaraco.text
# 使用显式UTF-8编码写入文件
hook_content = """
# 自定义pkg_resources钩子文件
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 排除有问题的模块
excludedimports = ['pkg_resources.py2_warn', 'setuptools', 'jaraco.text']

# 收集pkg_resources的数据文件
datas = collect_data_files('pkg_resources')
"""

with open(hooks_dir / 'hook-pkg_resources.py', 'w', encoding='utf-8') as f:
    f.write(hook_content)

# 尝试更直接的方法 - 直接编辑spec文件
try:
    # 先尝试普通构建以生成spec文件
    os.system('pyinstaller --name=视频批量上传 app.py --windowed --icon=logo.ico --noupx --clean')
    
    # 检查spec文件是否存在
    spec_file = Path('视频批量上传.spec')
    if spec_file.exists():
        # 读取spec文件
        with open(spec_file, 'r', encoding='utf-8') as f:
            spec_content = f.read()
        
        # 修改spec文件，添加必要的排除项
        if 'excludes=' in spec_content:
            spec_content = spec_content.replace(
                'excludes=[]', 
                "excludes=['setuptools', 'jaraco', 'more_itertools', 'packaging', 'pkg_resources.py2_warn']"
            )
        
        # 保存修改后的spec文件
        with open(spec_file, 'w', encoding='utf-8') as f:
            f.write(spec_content)
            
        # 使用修改后的spec文件构建
        print("🔄 使用修改后的spec文件构建...")
        os.system('pyinstaller --clean --noconfirm 视频批量上传.spec')
        print("✅ 构建完成！")
        sys.exit(0)
except Exception as e:
    print(f"❌ 修改spec文件失败: {e}")

# 如果上面的方法失败，回退到直接构建
print("⚠️ 回退到直接构建方法...")

# 准备参数列表
pyinstaller_args = [
    'app.py',                     # 主程序文件
    '--name=视频批量上传',         # 生成的exe名称
    '--windowed',                  # 使用GUI模式
    '--icon=logo.ico',            # 指定图标
    '--add-data=logo.ico;.',      # 将图标文件打包进exe
    f'--additional-hooks-dir={hooks_dir}',  # 使用自定义钩子
    '--exclude-module=setuptools',   # 排除setuptools
    '--exclude-module=jaraco',       # 排除整个jaraco命名空间
    '--exclude-module=more_itertools',  # 排除相关依赖
    '--exclude-module=packaging',    # 排除更多可能引起问题的模块
    '--onefile',                  # 打包成单个文件
    '--clean',                    # 清理临时文件
    '--noconfirm',                # 不确认覆盖
]

# 运行PyInstaller
print(f"🚀 开始构建，命令行参数: {' '.join(pyinstaller_args)}")
PyInstaller.__main__.run(pyinstaller_args) 
