
# setuptools 钩子
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

# 收集必要的子模块，排除可能导致问题的子模块
hiddenimports = [m for m in collect_submodules('setuptools') 
                if not any(x in m for x in ['jaraco', 'command.develop'])]

# 收集数据文件和元数据
datas = collect_data_files('setuptools') + copy_metadata('setuptools')
