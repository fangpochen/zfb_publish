
# pkg_resources 钩子
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

# 收集元数据，这很重要
datas = copy_metadata('pkg_resources') + collect_data_files('pkg_resources')

# 排除知道有问题的模块
excludedimports = ['pkg_resources.py2_warn', 'jaraco.text']
