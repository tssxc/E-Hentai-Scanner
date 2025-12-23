# app/common.py
"""
公共初始化函数，供 controller 和外部调用使用
"""
import os
from . import config

# 配置 UnRAR 工具路径（如果存在）
if config.UNRAR_PATH.exists():
    try:
        import rarfile
        rarfile.UNRAR_TOOL = str(config.UNRAR_PATH)
    except ImportError:
        pass  # rarfile 未安装时忽略

from .database import DatabaseManager
from .network import EHentaiHashSearcher
from .translator import TagTranslator
from .task_manager import TaskManager
from .result_handler import ResultHandler
from .logger import get_logger


def initialize_components():
    """
    初始化所有必要的组件
    
    Returns:
        tuple: (db, searcher, translator, task_manager, handler)
    """
    target_dir = config.DEFAULT_DIR
    current_table = config.TARGET_TABLE
    
    logger = get_logger(__name__)
    
    try:
        db = DatabaseManager(config.DB_PATH, table_name=current_table)
        
        # 自动备份
        db.create_backup()
        
        searcher = EHentaiHashSearcher(cookies=config.MY_COOKIES)
        translator = TagTranslator(str(config.TAG_DB_PATH))
        task_manager = TaskManager(db)
        handler = ResultHandler(db, translator)
        
        return db, searcher, translator, task_manager, handler, target_dir, current_table
        
    except Exception as e:
        logger.critical(f"🛑 初始化失败: {e}")
        raise


def verify_environment(searcher, target_dir):
    """
    验证环境和连接
    
    Args:
        searcher: EHentaiHashSearcher 实例
        target_dir: 目标目录路径（字符串或 Path 对象）
        
    Returns:
        bool: 验证是否通过
    """
    if not searcher.verify_connection():
        return False
    from pathlib import Path
    if not Path(target_dir).exists():
        return False
    return True

