#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
打包脚本 - 将程序打包成单个可执行文件
确保包含fonts目录中的字体文件和所有必要的资源
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import platform
import glob
import importlib.util

def 确保依赖安装():
    """确保必要的依赖已安装"""
    print("检查并安装必要的依赖...")
    dependencies = [
        "pyinstaller>=5.13.0",  # 使用最新的稳定版本
        "PyQt5>=5.15.0",
        "setuptools>=40.0.0",
        "pyinstaller-hooks-contrib>=2023.0",  # 确保有最新的钩子
        "certifi",  # 确保安装了certifi包
        "requests>=2.25.0"  # 确保安装了最新的requests
    ]
    
    for dep in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", dep])
            print(f"✅ 已安装/更新: {dep}")
        except Exception as e:
            print(f"⚠️ 安装 {dep} 时出错: {e}")
            print(f"  错误详情: {str(e)}")

def 清理旧构建文件():
    """清理之前的构建文件"""
    print("清理之前的构建文件...")
    paths_to_clean = ["build", "dist", "__pycache__", "*.spec"]
    
    for path_pattern in paths_to_clean:
        if '*' in path_pattern:
            # 处理通配符模式
            for path in glob.glob(path_pattern):
                if os.path.isfile(path):
                    os.remove(path)
                    print(f"已删除文件: {path}")
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                    print(f"已删除目录: {path}")
        else:
            # 处理具体路径
            if os.path.exists(path_pattern):
                if os.path.isfile(path_pattern):
                    os.remove(path_pattern)
                    print(f"已删除文件: {path_pattern}")
                else:
                    shutil.rmtree(path_pattern)
                    print(f"已删除目录: {path_pattern}")

def 收集项目模块():
    """收集项目中的所有Python模块"""
    print("收集项目模块...")
    模块列表 = []
    
    # 扫描项目根目录下的所有.py文件
    for py_file in glob.glob("*.py"):
        module_name = os.path.splitext(py_file)[0]
        模块列表.append(module_name)
    
    # 明确添加关键模块
    必须模块 = [
        "account_manager",
        "database",
        "upload_controller",
        "video_analyzer",
        "folder_manager",
        "api_client"
    ]
    
    for module in 必须模块:
        if module not in 模块列表:
            模块列表.append(module)
            print(f"明确添加必要模块: {module}")
    
    # 扫描项目目录下的子目录
    for dir_name in ["utils", "ui"]:
        if os.path.exists(dir_name) and os.path.isdir(dir_name):
            for root, dirs, files in os.walk(dir_name):
                for file in files:
                    if file.endswith('.py'):
                        # 将路径格式化为模块名称
                        file_path = os.path.join(root, file)
                        module_path = os.path.splitext(file_path)[0].replace(os.path.sep, '.')
                        模块列表.append(module_path)
    
    print(f"收集到 {len(模块列表)} 个项目模块")
    return 模块列表

def 收集资源文件():
    """收集需要打包的资源文件"""
    print("收集资源文件...")
    资源列表 = []
    
    # 将程序文件直接复制到根目录
    # 这样避免了在临时目录解压后可能导致的路径问题
    资源列表.append("--runtime-tmpdir=.")
    
    # 定义不包含的敏感文件和目录
    排除文件 = [
        # 密钥和证书文件
        "key.json", "api_key.txt", "secret.key", "*.key", "key_*.py", 
        "private_key.pem", "*.pem", "*.p12", "*.pfx", "*.cer",
        
        # 配置和凭证文件
        "config.json", "credentials.json", "auth.json", "settings.json",
        "config_*.json", "settings_*.json", "user_config.json", 
        
        # 令牌相关文件
        "token.txt", "oauth.json", "refresh_token.txt", "token_*.txt",
        
        # 通配符模式
        "*secret*", "*password*", "*token*", "*apikey*", "*key*", "*auth*", "*credential*",
        "*login*", "*session*", "*cookie*", "*account*",
        
        # 中文命名的密钥文件
        "密钥.txt", "密码.txt", "认证.txt", "KEY.txt", "授权.txt", "秘钥.*", 
        "账号.txt", "登录.txt", "配置.json", "设置.json",
        
        # 特定应用程序的密钥文件
        "key_verification.py", "key_verification.pyc",
        
        # 项目特定的敏感文件
        ".env", "env.py", "environment.py", "secrets.py", "secrets.json",
        
        # 数据库文件 - 确保用户数据不被打包
        "*.db", "*.sqlite", "*.sqlite3", "data.db", "app.db", "user.db", "account.db",
        "video.db", "zfb.db", "*.mdb", "*.accdb", "database/*",
        
        # 日志文件
        "*.log", "logs/*", "log/*", "*.log.*",
        
        # 缓存文件
        "__pycache__/*", "*.pyc", "*.pyo", "*.pyd", ".cache/*", "cache/*",
        "*.tmp", "temp/*", "tmp/*", 
        
        # 用户数据目录
        "user_data/*", "userdata/*", "user/*", "data/*", "uploads/*", "download/*",
        
        # 其他可能包含敏感信息的文件
        "history.txt", "cookies.txt", "session.json", "accounts.json", "passwords.txt"
    ]
    
    print("以下敏感文件类型将被排除打包:")
    for 文件 in 排除文件:
        print(f" - {文件}")
    
    # 添加fonts目录下的所有文件
    fonts_path = Path("fonts")
    if fonts_path.exists() and fonts_path.is_dir():
        # 整个fonts目录打包
        separator = ';' if platform.system() == 'Windows' else ':'
        资源列表.append(f"--add-data=fonts{separator}fonts")
        print(f"添加字体目录: fonts/")
    else:
        print("⚠️ 警告: fonts目录不存在!")
    
    # 添加其他可能需要的资源目录
    资源目录列表 = ["assets", "images", "ui"]  # 移除 utils 和 data 目录，因为它们可能包含敏感信息
    for 目录 in 资源目录列表:
        if os.path.exists(目录) and os.path.isdir(目录):
            separator = ';' if platform.system() == 'Windows' else ':'
            资源列表.append(f"--add-data={目录}{separator}{目录}")
            print(f"添加资源目录: {目录}/")
    
    # 添加配置文件和图标，但排除敏感文件
    附加文件 = ["logo.ico", "logo.png", "config.json.example", "favorite_topics.json"]
    for 文件 in 附加文件:
        if os.path.exists(文件):
            # 检查是否是敏感文件
            应该排除 = False
            for 排除模式 in 排除文件:
                if "*" in 排除模式:
                    # 处理通配符
                    import fnmatch
                    if fnmatch.fnmatch(文件.lower(), 排除模式.lower()):
                        应该排除 = True
                        break
                elif 文件.lower() == 排除模式.lower():
                    应该排除 = True
                    break
            
            if not 应该排除:
                separator = ';' if platform.system() == 'Windows' else ':'
                资源列表.append(f"--add-data={文件}{separator}.")
                print(f"添加文件: {文件}")
            else:
                print(f"排除敏感文件: {文件}")
    
    # 添加certifi证书文件
    try:
        import certifi
        cert_path = certifi.where()
        if os.path.exists(cert_path):
            separator = ';' if platform.system() == 'Windows' else ':'
            资源列表.append(f"--add-data={cert_path}{separator}certifi")
            print(f"添加证书文件: {cert_path}")
        else:
            print(f"⚠️ 警告: certifi证书文件不存在: {cert_path}")
    except ImportError:
        print("⚠️ 警告: 未安装certifi模块，请先安装")
    
    # 添加排除文件选项
    for 排除模式 in 排除文件:
        if "*" in 排除模式:
            资源列表.append(f"--exclude-module={排除模式}")
            # 添加文件排除选项
            资源列表.append(f"--exclude={排除模式}")
        else:
            资源列表.append(f"--exclude={排除模式}")
    
    # 显式排除key_verification模块和其他敏感模块
    敏感模块 = [
        "key_verification", "key_verification.py", 
        "secrets", "auth", "credentials", 
        "user_data", "user_settings"
    ]
    
    for 模块 in 敏感模块:
        资源列表.append(f"--exclude={模块}")
        资源列表.append(f"--exclude-module={模块}")
    
    # 确保数据库文件被排除
    资源列表.append("--exclude=*.db")
    资源列表.append("--exclude=database/*")
    
    # 确保配置被排除
    资源列表.append("--exclude=config.json")
    资源列表.append("--exclude=settings.json")
    
    # 排除用户数据目录
    资源列表.append("--exclude=user_data/*")
    资源列表.append("--exclude=data/*")
    
    return 资源列表

def 检测入口文件():
    """检测有效的入口文件"""
    print("检测入口文件...")
    
    # 检查main.py是否可用
    if os.path.exists("main.py"):
        # 检查main.py的内容是否有效
        try:
            with open("main.py", "r", encoding="utf-8") as f:
                内容 = f.read()
                if "if __name__ == \"__main__\"" in 内容:
                    print("检测到有效的main.py入口文件")
                    return "main.py"
        except Exception as e:
            print(f"读取main.py时出错: {e}")
    
    # 检查app.py是否可用
    if os.path.exists("app.py"):
        try:
            with open("app.py", "r", encoding="utf-8") as f:
                内容 = f.read()
                if "if __name__ == '__main__'" in 内容:
                    print("检测到有效的app.py入口文件")
                    return "app.py"
        except Exception as e:
            print(f"读取app.py时出错: {e}")
    
    # 其他可能的入口文件
    可能入口文件 = ["ui.py", "run.py", "start.py"]
    for 文件 in 可能入口文件:
        if os.path.exists(文件):
            print(f"使用替代入口文件: {文件}")
            return 文件
    
    print("⚠️ 警告: 无法检测到有效的入口文件，将使用main.py")
    return "main.py"

def 创建启动器脚本(入口文件):
    """创建启动器脚本来避免循环启动问题"""
    print("创建启动器脚本...")
    
    # 创建启动器目录
    launcher_dir = Path("launcher")
    launcher_dir.mkdir(exist_ok=True)
    
    # 创建启动器Python脚本
    launcher_content = f"""#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
启动器脚本 - 用于避免循环启动问题
'''

import os
import sys
import random
import time
import uuid
import tempfile

# 生成唯一的运行标识，防止重复启动
RUN_ID = str(uuid.uuid4())
LOCK_FILE = os.path.join(tempfile.gettempdir(), 'zfb_app_lock')

def check_already_running():
    # 检查是否已经有实例在运行
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, 'r') as f:
                existing_pid = f.read().strip()
                # 检查进程是否存在
                try:
                    # 对于Windows
                    if sys.platform.startswith('win'):
                        import ctypes
                        kernel32 = ctypes.windll.kernel32
                        handle = kernel32.OpenProcess(1, False, int(existing_pid))
                        if handle != 0:
                            kernel32.CloseHandle(handle)
                            print(f"程序已经在运行，进程ID: {{existing_pid}}")
                            return True
                    # 对于Unix-like系统
                    else:
                        import signal
                        os.kill(int(existing_pid), 0)
                        print(f"程序已经在运行，进程ID: {{existing_pid}}")
                        return True
                except (OSError, ValueError):
                    # 进程不存在，可以继续
                    pass
                
        # 创建锁文件
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        return False
    except Exception as e:
        print(f"检查程序运行状态时出错: {{e}}")
        return False

def clean_up():
    # 退出时清理锁文件
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except:
        pass

def main():
    # 检查是否已经有实例在运行
    if check_already_running():
        print("检测到程序已经在运行，不再启动新实例")
        sys.exit(0)
    
    # 注册清理函数
    import atexit
    atexit.register(clean_up)
    
    # 设置环境变量表明这是通过启动器启动的
    os.environ['ZFB_APP_LAUNCHER'] = RUN_ID
    
    # 获取可执行文件所在的目录
    if getattr(sys, 'frozen', False):
        # 打包后的可执行文件路径
        base_dir = os.path.dirname(sys.executable)
    else:
        # 开发环境中脚本路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 将工作目录设置为可执行文件所在目录
    os.chdir(base_dir)
    
    # 修改Python导入路径
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    
    # 添加可能需要的其他目录到路径
    for dir_name in ['ui', 'utils', 'assets', 'data']:
        dir_path = os.path.join(base_dir, dir_name)
        if os.path.exists(dir_path) and dir_path not in sys.path:
            sys.path.insert(0, dir_path)
    
    # 设置证书环境变量
    cert_dir = os.path.join(base_dir, 'certifi')
    if os.path.exists(cert_dir):
        pem_files = [f for f in os.listdir(cert_dir) if f.endswith('.pem')]
        if pem_files:
            cert_path = os.path.join(cert_dir, pem_files[0])
            os.environ['SSL_CERT_FILE'] = cert_path
            os.environ['REQUESTS_CA_BUNDLE'] = cert_path
    
    # 设置字体目录
    fonts_dir = os.path.join(base_dir, 'fonts')
    if os.path.exists(fonts_dir):
        os.environ['QT_QPA_FONTDIR'] = fonts_dir
    
    # 设置全局异常处理
    def exception_handler(exc_type, exc_value, exc_traceback):
        import traceback
        import datetime
        
        # 创建日志目录
        log_dir = os.path.join(base_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # 创建日志文件
        log_file = os.path.join(log_dir, f'error_{{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}}.log')
        
        # 写入日志
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\\n[{{datetime.datetime.now()}}] 未捕获的异常:\\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
        
        # 调用原始处理器
        return sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    # 设置全局异常处理器
    sys.excepthook = exception_handler
    
    # 导入并启动实际应用程序
    try:
        import {入口文件.replace('.py', '')}
        if '__main__' in dir({入口文件.replace('.py', '')}) and callable({入口文件.replace('.py', '')}.__main__):
            {入口文件.replace('.py', '')}.__main__()
        elif 'main' in dir({入口文件.replace('.py', '')}) and callable({入口文件.replace('.py', '')}.main):
            {入口文件.replace('.py', '')}.main()
        else:
            print("找不到程序入口函数，尝试直接导入该模块")
    except Exception as e:
        print(f"启动应用程序时出错: {{e}}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    # 添加随机延迟，防止多个实例同时启动时的竞争条件
    time.sleep(random.uniform(0.1, 0.5))
    main()
"""
    
    launcher_file = launcher_dir / "launcher.py"
    with open(launcher_file, "w", encoding="utf-8") as f:
        f.write(launcher_content)
        print(f"创建启动器脚本: {launcher_file}")
    
    return launcher_file

def 创建运行时钩子():
    """创建运行时钩子来处理导入问题"""
    print("创建运行时钩子...")
    
    # 创建runtime_hooks目录
    hooks_dir = Path("runtime_hooks")
    hooks_dir.mkdir(exist_ok=True)
    
    # 简化的钩子 - 避免过多的操作
    simple_hook = """
import os
import sys

# 设置工作目录和Python路径
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
    sys.path.insert(0, base_dir)
    
    # 检查是否通过启动器启动
    launcher_id = os.environ.get('ZFB_APP_LAUNCHER', '')
    if not launcher_id:
        print("警告：程序不是通过启动器启动的，可能会出现问题")
"""
    
    # 写入钩子文件
    with open(hooks_dir / "simple_hook.py", "w", encoding="utf-8") as f:
        f.write(simple_hook)
        print("创建简化钩子文件: simple_hook.py")
    
    return hooks_dir

def 创建首次运行标志():
    """创建首次运行标志文件，用于判断程序是否是第一次启动"""
    print("创建首次运行标志文件...")
    
    # 创建标志文件目录
    标志目录 = Path("flags")
    标志目录.mkdir(exist_ok=True)
    
    # 写入首次运行标志文件
    with open(标志目录 / "FIRST_RUN", "w", encoding="utf-8") as f:
        f.write("1")  # 1表示首次运行
    
    # 确保添加到打包资源中
    print("将首次运行标志添加到打包资源中")
    return 标志目录

def 执行打包():
    """执行PyInstaller打包"""
    print("开始执行打包...")
    
    # 收集资源文件
    资源列表 = 收集资源文件()
    
    # 检测入口文件
    入口文件 = 检测入口文件()
    
    # 创建启动器脚本
    launcher_file = 创建启动器脚本(入口文件)
    
    # 创建运行时钩子
    hooks_dir = 创建运行时钩子()
    
    # 创建首次运行标志
    标志目录 = 创建首次运行标志()
    
    # 添加标志目录到资源
    separator = ';' if platform.system() == 'Windows' else ':'
    资源列表.append(f"--add-data={标志目录}{separator}{标志目录}")
    
    # 收集项目模块
    项目模块 = 收集项目模块()
    
    # 构建命令 - 使用启动器脚本作为入口
    命令 = [
        sys.executable, "-m", "PyInstaller",
        "--name=支付宝上传和分析工具",
        "--onefile",  # 打包成单个文件
        "--console",  # 显示控制台窗口以便查看报错信息（调试用）
        f"--runtime-hook={hooks_dir/'simple_hook.py'}",
        "--key=", # 不使用加密密钥
    ]
    
    # 添加图标
    if os.path.exists("logo.ico"):
        命令.append("--icon=logo.ico")
    
    # 添加资源文件
    命令.extend(资源列表)
    
    # 添加隐藏导入模块 - 确保项目所有依赖都被包含
    隐藏导入 = [
        # PyQt5核心模块
        "PyQt5.QtWidgets",
        "PyQt5.QtCore", 
        "PyQt5.QtGui",
        "PyQt5.sip",
        
        # 项目中使用的模块
        "requests",
        "urllib3",
        "sqlite3",
        "pandas",
        "cryptography",
        "concurrent.futures",
        "threading",
        "json",
        "datetime",
        "numpy",
        "zipfile",
        "logging",
        "multiprocessing",
        "ast",
        "warnings",
        "certifi",
        "ssl",
        "socket",
        "PIL",
        "time",
        "os",
        "sys",
        "platform",
        "shutil",
        "uuid",
        "re",
        "random",
        
        # 项目特定模块 - 确保这些模块一定被包含，但排除敏感模块
        # "key_verification",  # 排除验证模块
        "database",
        "recommend_analysis_ui",
        "account_manager",  # 账号管理模块
        "folder_manager",
        "video_analyzer",
        "chart_manager",
        "upload_controller",
        "api_client",
        "utils.queue_manager",
        "utils.thread_pool",
        "utils.upload_controller",
        "utils.upload_processor",
        "utils.upload_statistics",
        "utils.video_task",
    ]
    
    # 添加项目中收集的模块
    敏感关键字 = ["key", "secret", "auth", "password", "token", "login", "session", "cookie", "config", "setting"]
    for 模块 in 项目模块:
        if not any(关键字 in 模块.lower() for 关键字 in 敏感关键字):
            隐藏导入.append(模块)
    
    # 添加入口文件模块
    入口模块 = 入口文件.replace('.py', '')
    if 入口模块 not in 隐藏导入:
        隐藏导入.append(入口模块)
    
    # 去重并排序
    隐藏导入 = sorted(set(隐藏导入))
    
    for 模块 in 隐藏导入:
        命令.append(f"--hidden-import={模块}")
    
    # 证书处理相关选项
    命令.append("--hidden-import=certifi.core")
    命令.append("--collect-all=certifi")
    命令.append("--collect-all=PyQt5")
    
    # 显式排除模块
    显式排除模块 = [
        "key_verification", "secrets", "auth", "credentials", 
        "user_data", "user_settings", "account_data", "password_manager",
        "config_manager", "session_handler", "cookie_store"
    ]
    
    for 模块 in 显式排除模块:
        命令.append(f"--exclude-module={模块}")
    
    # 添加额外选项
    命令.extend([
        "--clean",  # 构建前清理工作目录
        "--noconfirm",  # 不询问即覆盖
        "--strip",  # 移除符号表和调试信息
        str(launcher_file)  # 使用启动器作为入口
    ])
    
    # 执行命令
    print("执行命令:", " ".join(命令))
    try:
        result = subprocess.run(命令, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ PyInstaller 打包失败: {e}")
        尝试备用打包方案(入口文件, 项目模块, launcher_file)
        return False

def 尝试备用打包方案(入口文件, 项目模块=None, launcher_file=None):
    """当主要打包方案失败时，尝试备用打包方案"""
    print("⚠️ 尝试使用备用打包方案...")
    
    # 安装可能需要的额外依赖
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller-hooks-contrib"])
    
    # 如果launcher_file为None，创建一个启动器
    if launcher_file is None:
        launcher_file = 创建启动器脚本(入口文件)
    
    # 创建spec文件
    spec_内容 = f"""# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

block_cipher = None

# 定义资源文件
datas = []

# 添加fonts目录
if os.path.exists('fonts'):
    datas.append(('fonts', 'fonts'))

# 添加其他可能的资源目录
for dir_name in ['assets', 'data', 'ui', 'utils']:
    if os.path.exists(dir_name):
        datas.append((dir_name, dir_name))

# 添加单个文件
for file_name in ['logo.ico', 'logo.png', 'config.json.example', 'favorite_topics.json']:
    if os.path.exists(file_name):
        datas.append((file_name, '.'))

# 添加certifi证书文件
try:
    import certifi
    cert_path = certifi.where()
    if os.path.exists(cert_path):
        datas.append((cert_path, 'certifi'))
        print(f"添加证书文件: {{cert_path}}")
except ImportError:
    print("警告: 未安装certifi模块")

# 收集所有Python文件
py_files = []
for root, dirs, files in os.walk('.'):
    if '__pycache__' in root or '.git' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            file_path = os.path.join(root, file)
            py_files.append(file_path)

a = Analysis(
    ['{launcher_file}'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.sip',
        'requests', 'urllib3', 'sqlite3', 'pandas', 'cryptography', 'concurrent.futures',
        'threading', 'json', 'datetime', 'numpy', 'zipfile', 'logging',
        'multiprocessing', 'ast', 'warnings', 'certifi', 'ssl', 'socket',
        'PIL', 'time', 'os', 'sys', 'platform', 'shutil', 'uuid', 're', 'random',
        'key_verification', 'database', 'recommend_analysis_ui', 'account_manager',
        'folder_manager', 'video_analyzer', 'chart_manager', 'upload_controller',
        'api_client', '{入口文件.replace('.py', '')}'
    ] + {项目模块},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=['runtime_hooks/simple_hook.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='支付宝上传和分析工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=".",  # 设置为当前目录
    console=True,  # 使用控制台模式以便查看报错信息
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico' if os.path.exists('logo.ico') else None,
)
"""
    
    spec_文件名 = "支付宝上传和分析工具.spec"
    with open(spec_文件名, "w", encoding="utf-8") as f:
        f.write(spec_内容)
    
    print(f"创建spec文件: {spec_文件名}")
    
    # 使用spec文件打包
    命令 = [
        sys.executable, "-m", "PyInstaller",
        spec_文件名,
        "--clean",
        "--noconfirm"
    ]
    
    print("执行备用命令:", " ".join(命令))
    try:
        result = subprocess.run(命令, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 备用打包方案也失败了: {e}")
        return False

def 复制打包结果():
    """复制打包结果到当前目录"""
    print("复制打包结果...")
    dist_dir = Path("dist")
    if dist_dir.exists():
        for file in dist_dir.glob("*.exe"):
            shutil.copy(file, ".")
            print(f"已复制 {file} 到当前目录")
            return True
    print("⚠️ 警告: 没有找到打包结果")
    return False

def 创建无控制台版本(debug=False):
    """基于控制台版本，创建一个无控制台的生产版本"""
    if not debug:
        print("构建无控制台的生产版本...")
        
        # 修改spec文件
        spec_文件名 = "支付宝上传和分析工具.spec"
        if os.path.exists(spec_文件名):
            with open(spec_文件名, "r", encoding="utf-8") as f:
                spec_内容 = f.read()
            
            # 将console=True改为console=False
            spec_内容 = spec_内容.replace("console=True", "console=False")
            
            # 保存为新spec文件
            prod_spec_文件名 = "支付宝上传和分析工具_生产版.spec"
            with open(prod_spec_文件名, "w", encoding="utf-8") as f:
                f.write(spec_内容)
            
            # 使用新spec文件打包
            命令 = [
                sys.executable, "-m", "PyInstaller",
                prod_spec_文件名,
                "--clean",
                "--noconfirm"
            ]
            
            print("执行无控制台构建命令:", " ".join(命令))
            try:
                result = subprocess.run(命令, check=True)
                
                # 重命名生成的文件
                for file in Path("dist").glob("*.exe"):
                    新文件名 = str(file).replace("支付宝上传和分析工具", "支付宝上传和分析工具_生产版")
                    shutil.copy(file, 新文件名)
                    shutil.copy(新文件名, ".")
                    print(f"已复制 {新文件名} 到当前目录")
                
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ 构建无控制台版本失败: {e}")
                return False
        else:
            print(f"⚠️ 无法找到spec文件: {spec_文件名}")
            return False
    
    return True

def 主函数():
    """主函数"""
    print("=== 开始构建过程 ===")
    
    try:
        # 步骤1: 确保依赖已安装
        确保依赖安装()
        
        # 步骤2: 清理之前的构建
        清理旧构建文件()
        
        # 步骤3: 执行打包
        成功 = 执行打包()
        
        # 步骤4: 复制结果
        if 成功:
            复制打包结果()
            
            # 创建无控制台版本
            创建无控制台版本(debug=False)
            
            print("=== 构建过程完成! ===")
            print("调试版本 (带控制台) 位于 dist 目录和当前目录")
            print("生产版本 (无控制台) 也已创建")
            print("生产版使用前请先用调试版测试确认程序可以正常运行")
        else:
            print("=== 构建过程失败! ===")
            
    except Exception as e:
        print(f"❌ 构建过程出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(主函数())
