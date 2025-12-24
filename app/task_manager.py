# modules/task_manager.py
# modules/task_manager.py
import os
import random
import logging

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def get_pending_tasks(self, all_files, target_dir, is_debug=False, debug_count=5):
        """
        获取未入库的新文件
        """
        files_to_scan = []
        initial_count = len(all_files)
        
        logger.info(f"📋 开始任务筛选，总文件数: {initial_count}")

        if is_debug:
            files_to_scan = all_files
            if len(files_to_scan) > debug_count:
                files_to_scan = random.sample(files_to_scan, debug_count)
                logger.info(f"🔧 [Debug模式] 忽略历史记录，随机抽取 {len(files_to_scan)} 个文件")
            return files_to_scan, 0

        # 获取已处理列表
        logger.debug("正在从数据库拉取已处理文件列表...")
        processed_set = self.db.get_all_processed_paths()
        logger.debug(f"数据库中已有记录数: {len(processed_set)}")
        
        # 比对
        for f in all_files:
            # 统一路径格式处理，防止斜杠差异导致比对失败
            full_path = os.path.join(target_dir, f)
            # 也可以考虑只比对文件名，取决于数据库存储策略
            if full_path not in processed_set and f not in processed_set:
                files_to_scan.append(f)
            else:
                # logger.debug(f"跳过已存在: {f}") # 文件多时太吵，建议注释
                pass
        
        skipped_count = initial_count - len(files_to_scan)
        logger.info(f"✅ 筛选完成: 待处理 {len(files_to_scan)} | 已跳过 {skipped_count}")
        
        return files_to_scan, skipped_count

    def get_retry_tasks(self):
        """获取所有需要重试的任务"""
        sql = f"SELECT file_path FROM {self.db.table_name} WHERE status != 'SUCCESS'"
        logger.debug(f"执行 SQL: {sql}")
        
        try:
            self.db.cursor.execute(sql)
            rows = self.db.cursor.fetchall()
            paths = [row['file_path'] for row in rows]
            logger.info(f"找到 {len(paths)} 个待重试任务")
            return paths
        except Exception as e:
            logger.error(f"❌ 查询重试记录失败: {e}", exc_info=True)
            return []