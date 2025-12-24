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
        
        Args:
            db: 数据库管理器实例
            searcher: 网络搜索器实例
            task_manager: 任务管理器实例
            result_handler: 结果处理器实例
            validator: 验证器实例
        """
        # 直接接收外部传入的单例对象，不再自己 new
        self.db = db
        self.searcher = searcher
        self.task_manager = task_manager
        self.handler = result_handler
        self.validator = validator
        
        # 这里的验证逻辑由 Controller 统一管理，Service 层只需使用即可
        logger.debug("✅ ScanService 服务层加载完成")

    def get_pending_files(self, target_dir_str: str) -> List[Path]:
        """获取需要扫描的文件列表"""
        target_dir = Path(target_dir_str)
        if not target_dir.exists():
            logger.error(f"❌ 目录不存在: {target_dir}")
            return []
            
        # 1. 获取磁盘文件
        all_files = [f.name for f in target_dir.iterdir() 
                     if f.suffix.lower() in ('.zip', '.rar', '.cbz')]
        
        # 2. 使用 TaskManager 筛选
        # 注意：这里传入的是 str 类型的路径，适配 TaskManager
        new_names, skipped_count = self.task_manager.get_pending_tasks(
            all_files=all_files,
            target_dir=str(target_dir),
            is_debug=config.IS_DEBUG_MODE,
            debug_count=config.SCAN_LIMIT
        )
        
        # 3. 构造完整 Path 对象列表
        pending = [target_dir / name for name in new_names]
        
        logger.info(f"📂 目录总数: {len(all_files)} | 已入库(跳过): {skipped_count} | 待处理: {len(pending)}")
        return pending

    def scan_new_files(self, target_dir_str: str):
        """
        [业务入口] 扫描新文件
        """
        # 1. 获取任务
        files = self.get_pending_files(target_dir_str)
        
        # 2. 批量处理
        # 默认使用配置中的模式 (通常是 cover)
        self.process_batch(files, scan_mode=config.DEFAULT_MODE)

    def retry_failures(self, scan_mode='second'):
        """
        [业务入口] 重试失败任务
        """
        # 1. 获取所有非 SUCCESS 的任务路径
        retry_paths = self.task_manager.get_retry_tasks()
        
        if not retry_paths:
            logger.info("✅ 没有需要重试的任务")
            return

        # 2. 转换为 Path 对象
        files = [Path(p) for p in retry_paths if Path(p).exists()]
        
        logger.info(f"🔄 找到 {len(files)} 个待重试文件 (模式: {scan_mode})")
        
        # 3. 批量处理
        self.process_batch(files, scan_mode=scan_mode)

    def process_duplicates(self, scan_mode='second'):
        """
        [业务入口] 扫描重复 URL 的文件
        """
        # 1. 查找重复项
        count = self.db.find_and_store_url_duplicates()
        if count == 0:
            logger.info("✅ 未发现重复 URL")
            return

        logger.info(f"♻️ 发现 {count} 组重复 URL，准备去重扫描...")
        
        # 2. 获取任务 (这里假设 task_manager 有相应的方法，或者直接查库)
        # 简单起见，这里复用 retry 的逻辑，但在真实场景可能需要从 url_duplicates 表读取
        # 这里暂时留空或根据您的 check_duplicates.py 逻辑填充
        pass 

    def process_batch(self, files: List[Path], scan_mode: str = "cover"):
        """
        批量处理核心循环 (带验证与保护机制)
        """
        if not files:
            logger.info("✅ 任务列表为空")
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
                logger.warning(f"   🛡️ [保护机制] 匹配度低，已存为 MISMATCH")
                self.db.save_record(file_path, 'MISMATCH', scan_url, save_title, save_tags)
        
        else:
            # 处理无结果或错误
            status = 'NO_MATCH'
            error_msg = res.get('error') or res.get('message', '')
            
            # 状态映射
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
        
        # 返回结果用于显示
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

    def scan_single_file(self, file_path: str, scan_mode: str = 'cover'):
        """兼容 Controller 调用的别名方法"""
        return self.scan_single(file_path, scan_mode)

    def close(self):
        """关闭服务，释放资源"""
        if self.db:
            self.db.close()