# app/config.py
import os
import logging
from pathlib import Path

# ================= 🛡️ 全局模式开关 =================
# True  = 调试模式 (使用测试表、测试文件夹、详细日志、限制数量)
# False = 生产模式 (使用正式表、正式文件夹、普通日志、全量扫描)
IS_DEBUG_MODE = True

# ================= 📁 路径配置 (使用 pathlib) =================
# app/config.py -> app/ -> E-Hentai-Scanner/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 定义目录
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
TOOLS_DIR = PROJECT_ROOT / "tools"

# 自动创建目录
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 3. 数据库与资源路径
DB_PATH = DATA_DIR / "eh_scan_results.db"
TAG_DB_PATH = DATA_DIR / "db.text.json"

# 4. 日志文件路径
LOG_PATH_MAIN = LOG_DIR / "search_result.log"
LOG_PATH_RESCAN = LOG_DIR / "rescan.log"
LOG_PATH_APP = LOG_DIR / "app.log"

# --- 生产环境配置 (Production) ---
DIR_PROD = Path(r"D:\漫画")              # 正式漫画目录
TABLE_PROD = "scan_results"              # 正式表名

# --- 调试环境配置 (Debug) ---
DIR_DEBUG = Path(r"D:\漫画")              # 测试目录 (建议修改为实际测试路径)
TABLE_DEBUG = "scan_results_test"        # 测试表名

# ================= ⚙️ 逻辑自动切换 =================
if IS_DEBUG_MODE:
    DEFAULT_DIR = DIR_DEBUG
    TARGET_TABLE = TABLE_DEBUG
    LOG_LEVEL = logging.DEBUG
    SCAN_LIMIT = 5
    print(f"⚠️ [Config] 调试模式已激活! 操作表: {TARGET_TABLE} | 目录: {DEFAULT_DIR}")
else:
    DEFAULT_DIR = DIR_PROD
    TARGET_TABLE = TABLE_PROD
    LOG_LEVEL = logging.INFO
    SCAN_LIMIT = 0  # 0 代表不限制

# ================= 🔍 扫描设置 =================
DEFAULT_MODE = "cover"  # cover (封面) 或 second (第二页)

# ================= ⏱️ 访问频率控制 (秒) =================
SLEEP_MIN = 4.0
SLEEP_MAX = 5.0

# ================= 🛠️ UnRAR 工具路径 =================
UNRAR_PATH = TOOLS_DIR / "UnRAR.exe"

# ================= 🍪 用户凭证 =================
# 优先从 secrets.py 读取，如果不存在则尝试从环境变量读取
# 由于 secrets.py 在项目根目录，需要添加到路径
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from local_secrets import MY_COOKIES
except ImportError:
    MY_COOKIES = {
        'ipb_member_id': os.getenv('EH_IPB_MEMBER_ID', ''),
        'ipb_pass_hash': os.getenv('EH_IPB_PASS_HASH', ''),
        'igneous': os.getenv('EH_IGNEOUS', ''),
    }
    if not all(MY_COOKIES.values()):
        print("⚠️ 警告: 未找到 Cookie 配置! 请检查 secrets.py 或环境变量。")

