# app/services.py
"""
业务逻辑层：负责协调数据库、网络和文件系统
"""
import logging
from pathlib import Path
from typing import List, Optional, Union
from . import config
from .scanner_core import scan_single_file
from .utils import perform_random_sleep
from .logger import get_logger

logger = get_logger(__name__)

class ScanService:
    """
    扫描服务：封装所有扫描相关的业务逻辑
    """
    def __init__(self, db, searcher, task_manager, result_handler, validator):
        """
        初始化服务组件 (依赖注入模式)
        """
        self.db = db
        self.searcher = searcher
        self.task_manager = task_manager
        self.handler = result_handler
        self.validator = validator
        
        logger.debug("✅ ScanService 服务层加载完成")

    def get_pending_files(self, target_dir_str: str) -> List[Path]:
        target_dir = Path(target_dir_str)
        if not target_dir.exists():
            logger.error(f"❌ 目录不存在: {target_dir}")
            return []
            
        all_files = [f.name for f in target_dir.iterdir() 
                     if f.suffix.lower() in ('.zip', '.rar', '.cbz')]
        
        new_names, skipped_count = self.task_manager.get_pending_tasks(
            all_files=all_files,
            target_dir=str(target_dir),
            is_debug=config.IS_DEBUG_MODE,
            debug_count=config.SCAN_LIMIT
        )
        
        pending = [target_dir / name for name in new_names]
        logger.info(f"📂 目录总数: {len(all_files)} | 已入库(跳过): {skipped_count} | 待处理: {len(pending)}")
        return pending

    def scan_new_files(self, target_dir_str: str):
        """[业务入口] 扫描新文件"""
        files = self.get_pending_files(target_dir_str)
        self.process_batch(files, scan_mode=config.DEFAULT_MODE)

    def retry_failures(self, scan_mode='second'):
        """[业务入口] 重试失败任务"""
        retry_paths = self.task_manager.get_retry_tasks()
        if not retry_paths:
            logger.info("✅ 没有需要重试的任务")
            return
        files = [Path(p) for p in retry_paths if Path(p).exists()]
        logger.info(f"🔄 找到 {len(files)} 个待重试文件 (模式: {scan_mode})")
        self.process_batch(files, scan_mode=scan_mode)

    def process_duplicates(self, scan_mode='second'):
        """[业务入口] 扫描重复 URL 的文件"""
        count = self.db.find_and_store_url_duplicates()
        if count == 0:
            logger.info("✅ 未发现重复 URL")
            return
        logger.info(f"♻️ 发现 {count} 组重复 URL，请使用 check_duplicates.py 工具查看详情")

    def process_batch(self, files: List[Path], scan_mode: str = "cover"):
        if not files:
            logger.info("✅ 任务列表为空")
            return
        
        total = len(files)
        logger.info(f"🚀 开始批量扫描 {total} 个文件 (模式: {scan_mode})")

        for idx, file_path in enumerate(files, 1):
            file_str = str(file_path)
            logger.info(f"[{idx}/{total}] 处理: {file_path.name}")
            self._process_single_file_protected(file_str, scan_mode)

    def _process_single_file_protected(self, file_path: str, scan_mode: str):
        """
        [核心] 处理单个文件
        """
        perform_random_sleep()

        # 1. 执行扫描
        # 注意：这里调用下去后，ResultHandler 已经在内部完成了：
        #    a. 获取 URL
        #    b. Validator 验证 (获取元数据、计算相似度)
        #    c. 写入数据库 (SUCCESS / MISMATCH / FAIL)
        res = scan_single_file(
            file_path=file_path,
            searcher=self.searcher,
            handler=self.handler,
            scan_mode=scan_mode
        )

        # 2. [修复] 移除所有冗余逻辑
        # Service 层不再重复验证，只负责打印简单的流程日志
        if res['success']:
             # 成功日志已经在 ResultHandler 里打印了，这里可以保持沉默或简单记录
             pass
        else:
             # 只有出错时才在这里补一句日志，方便定位
             status = res.get('status', 'ERROR')
             msg = res.get('message', '')
             if status != 'NO_MATCH': # NO_MATCH 已经在 Handler 里 log 过了
                 logger.debug(f"   -> 流程结束: {status} ({msg})")

    def scan_single(self, file_path: Union[str, Path], scan_mode: Optional[str] = None) -> dict:
        scan_mode = scan_mode or config.DEFAULT_MODE
        path_str = str(file_path)
        self._process_single_file_protected(path_str, scan_mode)
        
        # 返回结果用于 CLI 显示
        record = self.db.get_record_by_path(path_str)
        if record:
            return {
                'success': record['status'] == 'SUCCESS',
                'status': record['status'],
                'message': f"状态: {record['status']} | Title: {record['title']}",
                'url': record['gallery_url'],
                'title': record['title']
            }
        return {'success': False, 'message': "未生成记录"}
        
    def close(self):
        if self.db:
            self.db.close()