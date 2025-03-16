
# packaging 钩子
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

# 收集所有子模块
hiddenimports = collect_submodules('packaging')

# 收集数据文件和元数据
datas = collect_data_files('packaging') + copy_metadata('packaging')
