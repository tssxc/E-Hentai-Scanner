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
    
    # [优化] 移除启动自动备份，改为按需备份或定期备份，提高启动速度
    # db_manager.create_backup()

    # 2. 网络搜索器
    try:
        from secrets import MY_COOKIES
    except ImportError:
        MY_COOKIES = getattr(config, 'MY_COOKIES', None)

    searcher = EHentaiHashSearcher(cookies=MY_COOKIES)
    
    # 验证网络 (仅警告，不阻塞)
    if not searcher.verify_connection():
        logger.warning("⚠️ 网络连接验证失败，扫描可能会受阻")

    # 3. 翻译器 (懒加载，瞬间完成)
    translator = TagTranslator(config.TAG_DB_PATH)
    
    # 4. 验证器 (核心判定逻辑)
    validator = ScanValidator(searcher, translator)

    # 5. 任务管理器
    task_manager = TaskManager(db_manager)

    # 6. 结果处理器 (传入 validator 以统一判定标准)
    result_handler = ResultHandler(db_manager, validator)

    logger.debug("✅ 所有组件初始化完成")
    
    return db_manager, searcher, translator, task_manager, result_handler, validator

def verify_environment():
    """环境目录自检"""
    if not config.DATA_DIR.exists():
        logger.info(f"创建数据目录: {config.DATA_DIR}")
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        
    if not config.LOG_DIR.exists():
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
    if not config.UNRAR_PATH.exists():
        logger.warning(f"⚠️ 未找到 UnRAR: {config.UNRAR_PATH}")