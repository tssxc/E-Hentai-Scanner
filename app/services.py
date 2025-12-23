# app/services.py
"""
业务逻辑层：负责协调数据库、网络和文件系统
"""
import logging
from pathlib import Path
from typing import List, Optional, Union
from . import config
from .database import DatabaseManager
from .network import EHentaiHashSearcher
from .translator import TagTranslator
from .task_manager import TaskManager
from .result_handler import ResultHandler
from .scanner_core import scan_single_file, run_batch_scan
from .utils import perform_random_sleep
from .logger import get_logger

logger = get_logger(__name__)


class ScanService:
    """
    扫描服务：封装所有扫描相关的业务逻辑
    """
    def __init__(self):
        """初始化服务组件"""
        self.db = DatabaseManager(config.DB_PATH, table_name=config.TARGET_TABLE)
        self.searcher = EHentaiHashSearcher(cookies=config.MY_COOKIES)
        self.translator = TagTranslator(str(config.TAG_DB_PATH))
        self.task_manager = TaskManager(self.db)
        self.handler = ResultHandler(self.db, self.translator)
        
        # 初始化动作
        self.db.create_backup()
        if not self.searcher.verify_connection():
            logger.warning("⚠️ 网络连接不稳定")

    def get_pending_files(self, target_dir: Path) -> List[Path]:
        """获取需要扫描的文件列表"""
        if not target_dir.exists():
            logger.error(f"❌ 目录不存在: {target_dir}")
            return []
            
        # 1. 获取磁盘文件
        all_files = [f.name for f in target_dir.iterdir() 
                     if f.suffix.lower() in ('.zip', '.rar', '.cbz')]
        
        # 2. 使用 TaskManager 筛选
        new_names, skipped_count = self.task_manager.get_pending_tasks(
            all_files=all_files,
            target_dir=str(target_dir),
            is_debug=config.IS_DEBUG_MODE,
            debug_count=config.SCAN_LIMIT
        )
        
        # 3. 构造完整路径
        pending = [target_dir / name for name in new_names]
        
        logger.info(f"📂 目录总数: {len(all_files)} | 已入库(跳过): {skipped_count} | 待处理: {len(pending)}")
        return pending

    def process_batch(self, files: List[Path], scan_mode: str = "cover"):
        """批量处理核心循环"""
        if not files:
            logger.info("✅ 没有待处理文件")
            return
        
        # 转换为字符串列表以兼容现有接口
        file_paths = [str(f) for f in files]
        
        # 使用 scanner_core 的批量扫描函数
        run_batch_scan(
            tasks=file_paths,
            description="批量扫描",
            searcher=self.searcher,
            handler=self.handler,
            scan_mode=scan_mode
        )

    def scan_single(self, file_path: Union[str, Path], scan_mode: Optional[str] = None) -> dict:
        """扫描单个文件"""
        scan_mode = scan_mode or config.DEFAULT_MODE
        return scan_single_file(
            file_path=str(file_path),
            searcher=self.searcher,
            handler=self.handler,
            scan_mode=scan_mode
        )

    def get_retry_files(self) -> List[str]:
        """获取需要重试的文件列表（状态为 FAIL 或 NULL URL）"""
        return self.task_manager.get_null_url_tasks()

    def get_duplicate_files(self) -> List[str]:
        """获取重复 URL 的文件列表"""
        return self.task_manager.get_duplicate_tasks()

    def close(self):
        """关闭服务，释放资源"""
        if self.db:
            self.db.close()

