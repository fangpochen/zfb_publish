
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
