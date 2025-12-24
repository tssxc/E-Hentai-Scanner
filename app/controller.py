# app/controller.py
import logging
from pathlib import Path
from . import config
from .common import initialize_components, verify_environment
from .services import ScanService

logger = logging.getLogger(__name__)

class AppController:
    def __init__(self):
        # 1. 初始化所有组件 (接收6个返回值)
        (
            self.db, 
            self.searcher, 
            self.translator, 
            self.task_manager, 
            self.result_handler,
            self.validator
        ) = initialize_components()

        # 2. 注入到服务层
        self.service = ScanService(
            self.db, 
            self.searcher, 
            self.task_manager, 
            self.result_handler,
            self.validator
        )

    def scan_new_files(self):
        verify_environment()
        target_dir = config.DEFAULT_DIR
        
        if not target_dir.exists():
            logger.error(f"❌ 目标目录不存在: {target_dir}")
            return

        logger.info(f"📂 扫描目录: {target_dir}")
        self.service.scan_new_files(str(target_dir))

    def retry_failures(self):
        logger.info("🔄 准备重试失败任务...")
        self.service.retry_failures(scan_mode='second')

    def scan_dedup(self):
        logger.info("♻️ 开始去重扫描...")
        self.service.process_duplicates(scan_mode='second')

    def scan_single(self, file_path, scan_mode='cover'):
        path_obj = Path(file_path)
        if not path_obj.exists():
            logger.error(f"❌ 文件不存在: {file_path}")
            return
        logger.info(f"🔍 单文件扫描: {path_obj.name} (模式: {scan_mode})")
        self.service.scan_single_file(str(path_obj), scan_mode=scan_mode)

    def cleanup(self):
        if self.db:
            self.db.close()