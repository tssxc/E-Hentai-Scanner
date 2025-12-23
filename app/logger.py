# app/logger.py
"""
统一的日志配置模块
"""
import os
import logging
from . import config


def setup_logging(log_file_path, log_format=None):
    """
    配置日志系统
    
    Args:
        log_file_path: 日志文件路径（字符串或 Path 对象）
        log_format: 日志格式，如果为 None 则使用默认格式
    
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    from pathlib import Path
    # 确保日志目录存在
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 默认格式
    if log_format is None:
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
    
    # 配置根日志记录器
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format=log_format,
        handlers=[
            logging.FileHandler(str(log_file_path), encoding='utf-8'),
            logging.StreamHandler()
        ],
        force=True  # 允许重新配置已存在的日志系统
    )
    
    # 降低第三方库的日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


def get_logger(name):
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称（通常是 __name__）
    
    Returns:
        logging.Logger: 日志记录器实例
    """
    return logging.getLogger(name)

