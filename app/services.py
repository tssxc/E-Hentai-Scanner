# app/services.py
"""
业务逻辑层：负责协调数据库、网络和文件系统
"""
import logging
import os
from pathlib import Path
from typing import List, Optional, Union
from . import config
from .database import DatabaseManager
# 注意：这里移除了 .network 的引用，避免循环依赖，因为 network 已被底层调用
from .translator import TagTranslator
from .task_manager import TaskManager
from .result_handler import ResultHandler
from .scanner_core import scan_single_file
from .utils import perform_random_sleep
from .logger import get_logger
from .validator import ScanValidator
# 延迟导入以避免循环引用，或者在 __init__ 中处理
from .network import EHentaiHashSearcher

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
        
        # 初始化验证器
        self.validator = ScanValidator(self.searcher, self.translator)
        
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
        """
        批量处理核心循环 (带验证与保护机制)
        """
        if not files:
            logger.info("✅ 没有待处理文件")
            return
        
        total = len(files)
        logger.info(f"🚀 开始批量扫描 {total} 个文件 (模式: {scan_mode})")

        for idx, file_path in enumerate(files, 1):
            file_str = str(file_path)
            logger.info(f"[{idx}/{total}] 处理: {file_path.name}")
            
            # 执行带保护机制的单文件处理
            self._process_single_file_protected(file_str, scan_mode)

    def _process_single_file_protected(self, file_path: str, scan_mode: str):
        """
        [核心] 处理单个文件：扫描 -> 验证 -> 分级存储
        """
        path_obj = Path(file_path)
        file_name = path_obj.name
        clean_name = path_obj.stem
        
        perform_random_sleep()

        # 1. 执行扫描 (获取基础 URL)
        res = scan_single_file(
            file_path=file_path,
            searcher=self.searcher,
            handler=self.handler,
            scan_mode=scan_mode
        )

        # 2. 如果成功获取 URL，进行严格验证
        if res['success'] and res.get('url'):
            scan_url = res['url']
            
            # 调用验证器
            is_valid, title, tags = self.validator.evaluate_scan_result(clean_name, scan_url)
            
            # 确保字段非空
            save_title = title if title else (res.get('title') or "Unknown Title")
            save_tags = tags if tags else ""

            if is_valid:
                logger.info(f"   🎉 [验证通过] 匹配成功: {save_title[:30]}...")
                self.db.save_record(file_path, 'SUCCESS', scan_url, save_title, save_tags)
            else:
                # 保护机制: URL 有效但标题/Tag 不匹配 -> 存为 MISMATCH
                logger.warning(f"   🛡️ [保护机制] 匹配度低，已存为 MISMATCH: {scan_url}")
                self.db.save_record(file_path, 'MISMATCH', scan_url, save_title, save_tags)
        
        else:
            # 处理无结果或错误
            status = 'NO_MATCH'
            error_msg = res.get('error') or res.get('message', '')
            
            if "IP" in str(error_msg): status = 'ERROR'
            elif "Archive" in str(error_msg) or "FILE_ERROR" in str(error_msg): status = 'FILE_ERROR'
            elif res.get('status') == 'FAIL': status = 'NO_MATCH'
            else: status = res.get('status', 'ERROR')

            # 只有当原本不是 NO_MATCH 时才打印错误，减少刷屏
            if status != 'NO_MATCH':
                logger.error(f"   ❌ 扫描无果/出错: {status} | {error_msg}")
            else:
                logger.info(f"   🈚 无结果")
            
            self.db.save_record(file_path, status)

    def scan_single(self, file_path: Union[str, Path], scan_mode: Optional[str] = None) -> dict:
        """扫描单个文件 (暴露给 CLI 使用)"""
        scan_mode = scan_mode or config.DEFAULT_MODE
        path_str = str(file_path)
        self._process_single_file_protected(path_str, scan_mode)
        record = self.db.get_record_by_path(path_str)
        if record:
            return {
                'success': record['status'] == 'SUCCESS',
                'message': f"状态: {record['status']} | Title: {record['title']}"
            }
        return {'success': False, 'message': "未生成记录"}

    def get_retry_files(self) -> List[str]:
        """[修改] 获取需要重试的文件列表（所有非 SUCCESS）"""
        # 现在调用 TaskManager 的 get_retry_tasks
        return self.task_manager.get_retry_tasks()

    def get_duplicate_files(self) -> List[str]:
        """获取重复 URL 的文件列表"""
        return self.task_manager.get_duplicate_tasks()

    def close(self):
        """关闭服务，释放资源"""
        if self.db:
            self.db.close()