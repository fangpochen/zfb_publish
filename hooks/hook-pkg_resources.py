
# 自定义pkg_resources钩子文件
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 排除有问题的模块
excludedimports = ['pkg_resources.py2_warn', 'setuptools', 'jaraco.text']

# 收集pkg_resources的数据文件
datas = collect_data_files('pkg_resources')
