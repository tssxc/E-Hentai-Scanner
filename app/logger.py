# app/logger.py
"""
统一的日志配置模块
"""
import os
import logging
import sys
from pathlib import Path
from . import config

def setup_logging(log_file_path, log_format=None):
    """
    配置日志系统
    
    Args:
        log_file_path: 日志文件路径
        log_format: 日志格式
    """
    # 确保日志目录存在
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 优化：默认格式增加 文件名:行号，方便定位问题
    if log_format is None:
        log_format = '%(asctime)s - [%(levelname)s] - [%(filename)s:%(lineno)d] - %(message)s'
    
    # 配置根日志记录器
    handlers = [
        logging.FileHandler(str(log_file_path), encoding='utf-8'),
        logging.StreamHandler(sys.stdout) # 明确指定输出流
    ]
    
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format=log_format,
        handlers=handlers,
        force=True
    )
    
    # 降低由于重试机制产生的第三方库噪音
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    # 打印一条初始化日志
    logging.getLogger(__name__).debug(f"日志系统初始化完成，级别: {logging.getLevelName(config.LOG_LEVEL)}")
    
    return logging.getLogger(__name__)

def get_logger(name):
    return logging.getLogger(name)