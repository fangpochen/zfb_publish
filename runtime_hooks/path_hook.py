
import os
import sys
import traceback

def setup_paths():
    try:
        # 获取可执行文件所在的目录
        if getattr(sys, 'frozen', False):
            # 打包后的可执行文件路径
            base_dir = os.path.dirname(sys.executable)
            # 将基础目录添加到sys.path
            if base_dir not in sys.path:
                sys.path.insert(0, base_dir)
            
            # 添加可能需要的其他目录
            for dir_name in ['ui', 'utils', 'assets', 'data']:
                dir_path = os.path.join(base_dir, dir_name)
                if os.path.exists(dir_path) and dir_path not in sys.path:
                    sys.path.insert(0, dir_path)
                    print(f"添加目录到路径: {dir_path}")
        
        # 设置工作目录
        if getattr(sys, 'frozen', False):
            os.chdir(os.path.dirname(sys.executable))
            print(f"工作目录设置为: {os.path.dirname(sys.executable)}")
            
        # 打印调试信息
        print("Python路径:")
        for p in sys.path:
            print(f" - {p}")
    except Exception as e:
        print(f"设置路径时出错: {e}")
        traceback.print_exc()

setup_paths()
