"""pytest 根 conftest —— 把仓库根放进 sys.path。

flat layout：生产模块在仓库根，测试在 tests/。pytest 默认只把测试文件所在目录
（tests/）加进 sys.path，根模块（translation_postprocess 等）会 import 不到。
这里显式把根插到 sys.path 最前，稳过 import（不依赖 pytest import-mode 细节）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
