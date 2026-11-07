# 仓库路径集中管理（v43）：之前 18 个脚本硬编码 /workspace/projects/d6a0e27a-.../shici，
# 换台机器即失效。优先 SHIJIAN_ROOT 环境变量，否则按本文件位置推断仓库根。
# 用法：from paths import ROOT, BUILD, DATA, SITE, APP, PARENT
import os

ROOT = os.environ.get('SHIJIAN_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
DATA = os.path.join(ROOT, 'app', 'site', 'data')
SITE = os.path.join(ROOT, 'app', 'site')
APP = os.path.join(ROOT, 'app')
PARENT = os.path.dirname(ROOT)  # 放 chinese-classics / modern-poetry 等同级仓库的目录
