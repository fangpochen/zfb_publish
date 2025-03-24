#!/usr/bin/env python
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
                            print(f"程序已经在运行，进程ID: {existing_pid}")
                            return True
                    # 对于Unix-like系统
                    else:
                        import signal
                        os.kill(int(existing_pid), 0)
                        print(f"程序已经在运行，进程ID: {existing_pid}")
                        return True
                except (OSError, ValueError):
                    # 进程不存在，可以继续
                    pass
                
        # 创建锁文件
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        return False
    except Exception as e:
        print(f"检查程序运行状态时出错: {e}")
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
        log_file = os.path.join(log_dir, f'error_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        # 写入日志
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n[{datetime.datetime.now()}] 未捕获的异常:\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
        
        # 调用原始处理器
        return sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    # 设置全局异常处理器
    sys.excepthook = exception_handler
    
    # 导入并启动实际应用程序
    try:
        import main
        if '__main__' in dir(main) and callable(main.__main__):
            main.__main__()
        elif 'main' in dir(main) and callable(main.main):
            main.main()
        else:
            print("找不到程序入口函数，尝试直接导入该模块")
    except Exception as e:
        print(f"启动应用程序时出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    # 添加随机延迟，防止多个实例同时启动时的竞争条件
    time.sleep(random.uniform(0.1, 0.5))
    main()
