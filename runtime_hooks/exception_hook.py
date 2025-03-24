
import os
import sys
import traceback
import datetime

def setup_exception_handling():
    # 创建日志文件夹
    log_dir = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建日志文件
    log_file = os.path.join(log_dir, f'error_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    # 保存原始的异常处理器
    original_hook = sys.excepthook
    
    # 创建新的异常处理器
    def exception_handler(exc_type, exc_value, exc_traceback):
        # 写入日志文件
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n[{datetime.datetime.now()}] 未捕获的异常:\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
        
        # 打印到控制台
        print(f"发生未捕获异常，详细信息已保存到: {log_file}")
        print("异常详情:")
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        
        # 调用原始异常处理器
        return original_hook(exc_type, exc_value, exc_traceback)
    
    # 设置为新的异常处理器
    sys.excepthook = exception_handler
    print(f"已设置全局异常处理器，日志将保存到: {log_dir}")

setup_exception_handling()
