import subprocess
import sys
import os
import shutil
from pathlib import Path

# 确保必要的依赖已安装
def ensure_dependencies():
    print("检查并安装必要的依赖...")
    dependencies = [
        "pyinstaller>=5.0.0",
        "PyQt5>=5.15.0",
        "packaging",
        "setuptools>=40.0.0",
        "six>=1.10.0"
    ]
    
    for dep in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", dep])
            print(f"✅ 已安装/更新: {dep}")
        except Exception as e:
            print(f"⚠️ 安装 {dep} 时出错: {e}")

# 清理之前的构建文件
def clean_previous_build():
    print("清理之前的构建文件...")
    paths_to_clean = ["build", "dist", "hooks", "__pycache__", "视频批量上传.spec"]
    
    for path in paths_to_clean:
        if os.path.exists(path):
            if os.path.isfile(path):
                os.remove(path)
                print(f"已删除文件: {path}")
            else:
                shutil.rmtree(path)
                print(f"已删除目录: {path}")

# 准备钩子和数据文件
def prepare_hooks_and_data():
    print("准备钩子文件和数据文件...")
    # 创建钩子目录
    hooks_dir = Path("hooks")
    hooks_dir.mkdir(exist_ok=True)
    
    # 钩子文件定义
    hooks = {
        # 处理 pkg_resources 问题的钩子
        "hook-pkg_resources.py": """
# pkg_resources 钩子
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

# 收集元数据，这很重要
datas = copy_metadata('pkg_resources') + collect_data_files('pkg_resources')

# 排除知道有问题的模块
excludedimports = ['pkg_resources.py2_warn', 'jaraco.text']
""",
        # 处理 packaging 模块的钩子
        "hook-packaging.py": """
# packaging 钩子
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

# 收集所有子模块
hiddenimports = collect_submodules('packaging')

# 收集数据文件和元数据
datas = collect_data_files('packaging') + copy_metadata('packaging')
""",
        # 处理 setuptools 问题的钩子
        "hook-setuptools.py": """
# setuptools 钩子
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

# 收集必要的子模块，排除可能导致问题的子模块
hiddenimports = [m for m in collect_submodules('setuptools') 
                if not any(x in m for x in ['jaraco', 'command.develop'])]

# 收集数据文件和元数据
datas = collect_data_files('setuptools') + copy_metadata('setuptools')
""",
        # 处理 PyQt5 问题的钩子
        "hook-PyQt5.py": """
# PyQt5 钩子
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 确保所有 PyQt5 插件被正确打包
hiddenimports = collect_submodules('PyQt5')

# 收集数据文件
datas = collect_data_files('PyQt5')
""",
        # 主程序钩子，确保应用特定的模块被包含
        "hook-app.py": """
# 应用程序钩子
hiddenimports = [
    'packaging',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements',
    'packaging.markers',
    'pkg_resources.py2_warn',
    'sqlite3',
    'json',
    'datetime',
    'cv2',  # 如果使用 OpenCV
    'requests',
    'concurrent.futures',
    'pandas',
    'zipfile',
    'logging'
]
"""
    }
    
    # 写入钩子文件
    for filename, content in hooks.items():
        with open(hooks_dir / filename, "w", encoding="utf-8") as f:
            f.write(content)
            print(f"创建钩子文件: {filename}")
    
    # 创建运行时钩子来处理导入问题
    runtime_hooks_dir = Path("runtime_hooks")
    runtime_hooks_dir.mkdir(exist_ok=True)
    
    runtime_hook_content = """
# 运行时钩子 - 处理可能的导入问题
import os
import sys
import importlib

def hook_import(name, *args, **kwargs):
    try:
        return original_import(name, *args, **kwargs)
    except ImportError as e:
        # 尝试处理一些常见的导入错误
        if name == 'pkg_resources.py2_warn':
            # 创建一个假的模块
            class DummyModule: pass
            module = DummyModule()
            sys.modules[name] = module
            return module
        
        if name == 'packaging' or name.startswith('packaging.'):
            # 对于 packaging 相关模块，尝试直接加载 setuptools._vendor 中的版本
            try:
                vendor_name = name.replace('packaging', 'setuptools._vendor.packaging')
                return original_import(vendor_name, *args, **kwargs)
            except ImportError:
                pass
        
        # 其他错误继续抛出
        raise e

# 保存原始的 __import__ 函数
original_import = __import__
# 替换为我们的钩子函数
__builtins__['__import__'] = hook_import
"""
    
    with open(runtime_hooks_dir / "import_hook.py", "w", encoding="utf-8") as f:
        f.write(runtime_hook_content)
        print("创建运行时钩子: import_hook.py")
    
    return hooks_dir, runtime_hooks_dir

# 执行 PyInstaller 构建
def run_pyinstaller(hooks_dir, runtime_hooks_dir):
    print("开始执行 PyInstaller 构建...")
    
    # 确保logo.ico存在
    if not os.path.exists('logo.ico'):
        raise FileNotFoundError("logo.ico not found!")
    
    # 构建命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=视频批量上传",
        "--onefile",
        "--windowed",
        "--icon=logo.ico",
        "--add-data=logo.ico;.",
        f"--additional-hooks-dir={hooks_dir}",
        f"--runtime-hook={runtime_hooks_dir / 'import_hook.py'}",
        "--hidden-import=packaging",
        "--hidden-import=packaging.version",
        "--hidden-import=packaging.specifiers",
        "--hidden-import=packaging.requirements",
        "--hidden-import=packaging.markers",
        "--hidden-import=pkg_resources.py2_warn",
        "--hidden-import=concurrent.futures",
        "--hidden-import=sqlite3",
        "--hidden-import=pandas",
        "--hidden-import=PyQt5.QtCore",
        "--hidden-import=PyQt5.QtGui",
        "--hidden-import=PyQt5.QtWidgets",
        "--collect-all=PyQt5",
        "--clean",
        "--noconfirm",
        "app.py"
    ]
    
    # 执行 PyInstaller 命令
    print("执行命令:", " ".join(cmd))
    try:
        result = subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ PyInstaller 构建失败: {e}")
        return False

# 创建简化版的构建方式作为备用选项
def fallback_build():
    print("⚠️ 尝试使用简化的构建方式...")
    
    # 安装可能需要的额外依赖
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller-hooks-contrib"])
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=视频批量上传",
        "--onefile",
        "--windowed",
        "--icon=logo.ico",
        "--add-data=logo.ico;.",
        "--clean",
        "--noconfirm",
        "app.py"
    ]
    
    print("执行简化命令:", " ".join(cmd))
    try:
        result = subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 简化构建也失败了: {e}")
        return False

# 主函数
def main():
    try:
        print("=== 开始构建过程 ===")
        
        # 步骤1: 确保依赖已安装
        ensure_dependencies()
        
        # 步骤2: 清理之前的构建
        clean_previous_build()
        
        # 步骤3: 准备钩子和数据文件
        hooks_dir, runtime_hooks_dir = prepare_hooks_and_data()
        
        # 步骤4: 执行 PyInstaller 构建
        success = run_pyinstaller(hooks_dir, runtime_hooks_dir)
        
        # 如果失败，尝试备用方案
        if not success:
            success = fallback_build()
        
        if success:
            print("✅ 构建成功！可执行文件在 dist 目录中")
        else:
            print("❌ 构建失败")
        
    except Exception as e:
        print(f"构建过程中出现错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
