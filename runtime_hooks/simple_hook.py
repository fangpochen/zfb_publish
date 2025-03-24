
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
