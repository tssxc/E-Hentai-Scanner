# app/common.py
import logging
from . import config
from .database import DatabaseManager
from .network import EHentaiHashSearcher
from .result_handler import ResultHandler
from .task_manager import TaskManager
from .translator import TagTranslator
from .validator import ScanValidator 

logger = logging.getLogger(__name__)

def initialize_components():
    """
    初始化所有核心组件
    Returns:
        tuple: (db, searcher, translator, task_manager, result_handler, validator)
    """
    # 1. 数据库
    db_manager = DatabaseManager(config.DB_PATH, table_name=config.TARGET_TABLE)
    
    # 启动时自动备份数据库
    try:
        db_manager.create_backup()
    except Exception as e:
        logger.warning(f"⚠️ 自动备份失败: {e}")

    # 2. 网络搜索器
    try:
        from secrets import MY_COOKIES
    except ImportError:
        MY_COOKIES = getattr(config, 'MY_COOKIES', None)

    searcher = EHentaiHashSearcher(cookies=MY_COOKIES)
    
    # 验证网络
    if not searcher.verify_connection():
        logger.warning("⚠️ 网络连接验证失败，可能会影响扫描")

    # 3. 翻译器 [修复此处]
    # 必须传入 config.TAG_DB_PATH
    translator = TagTranslator(config.TAG_DB_PATH)
    
    # 4. 验证器
    validator = ScanValidator(searcher, translator)

    # 5. 任务管理器
    task_manager = TaskManager(db_manager)

    # 6. 结果处理器
    result_handler = ResultHandler(db_manager, validator)

    logger.debug("✅ 所有组件初始化完成")
    
    return db_manager, searcher, translator, task_manager, result_handler, validator

def verify_environment():
    """
    环境自检
    """
    if not config.DATA_DIR.exists():
        logger.info(f"创建数据目录: {config.DATA_DIR}")
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        
    if not config.LOG_DIR.exists():
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
    if not config.UNRAR_PATH.exists():
        logger.warning(f"⚠️ 未找到 UnRAR: {config.UNRAR_PATH}")
        logger.warning("   -> RAR 文件可能无法处理")