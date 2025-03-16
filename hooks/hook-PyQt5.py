
# PyQt5 钩子
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 确保所有 PyQt5 插件被正确打包
hiddenimports = collect_submodules('PyQt5')

# 收集数据文件
datas = collect_data_files('PyQt5')
