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
        获取未入库的新文件（标准扫描模式）
        """
        files_to_scan = []
        skipped_count = 0
        initial_count = len(all_files)

        if is_debug:
            files_to_scan = all_files
            if len(files_to_scan) > debug_count:
                files_to_scan = random.sample(files_to_scan, debug_count)
                logger.info(f"🔧 [Debug] 忽略历史记录，随机抽取 {len(files_to_scan)} 个文件")
            return files_to_scan, 0

        logger.info("📡 [断点续传] 正在比对数据库记录...")
        processed_set = self.db.get_all_processed_paths()
        
        for f in all_files:
            full_path = os.path.join(target_dir, f)
            if full_path not in processed_set:
                files_to_scan.append(f)
        
        skipped_count = initial_count - len(files_to_scan)
        
        if skipped_count > 0:
            logger.info(f"⏭️ 已跳过 {skipped_count} 个已完成文件")
        
        return files_to_scan, skipped_count

    def get_duplicate_tasks(self):
        """获取重复 URL 任务"""
        logger.info(f"🔍 [{self.db.table_name}] 正在检索重复 URL...")
        
        # [修改] 使用 self.db.table_name
        sql = f"""
        SELECT file_path, gallery_url 
        FROM {self.db.table_name} 
        WHERE gallery_url IN (
            SELECT gallery_url 
            FROM {self.db.table_name} 
            WHERE status = 'SUCCESS' AND gallery_url IS NOT NULL 
            GROUP BY gallery_url 
            HAVING COUNT(*) > 1
        )
        """
        try:
            self.db.cursor.execute(sql)
            rows = self.db.cursor.fetchall()
            paths = [row['file_path'] for row in rows]
            return paths
        except Exception as e:
            logger.error(f"❌ 查询重复失败: {e}")
            return []
    def get_null_url_tasks(self):
        """
        [新增] 获取数据库中 gallery_url 为 NULL 或空字符串的任务
        通常是上次扫描失败、无结果(NO_MATCH)或格式不支持的文件
        """
        logger.info("🔍 正在检索无有效 URL 的历史记录...")
        
        # SQL: 查找 url 字段为空 或 NULL 的记录
        sql = f"""
        SELECT file_path 
        FROM {self.db.table_name} 
        WHERE gallery_url IS NULL OR gallery_url = ''
        """
        try:
            self.db.cursor.execute(sql)
            rows = self.db.cursor.fetchall()
            paths = [row['file_path'] for row in rows]
            return paths
        except Exception as e:
            logger.error(f"❌ 查询 NULL 记录失败: {e}")
            return []