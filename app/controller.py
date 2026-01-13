# app/controller.py
import logging
import time
import random
from pathlib import Path
from typing import List, Optional

from . import config
from .database import DatabaseManager
from .network import EHentaiHashSearcher
from .services import ScannerService
from .translator import TagTranslator
from .deduplication import DeduplicationManager

logger = logging.getLogger(__name__)

class AppController:
    def __init__(self, table_name: Optional[str] = None):
        """
        :param table_name: 指定数据库表名。
                           如果不传，会优先尝试读取 config.TABLE_NAME (由 manage.py 设置)，
                           最后默认为 "scan_results" (生产环境)。
        """
        # 1. 确定表名逻辑: 参数 > 全局配置 > 默认值
        # 这样 manage.py 修改 config.TABLE_NAME 后，GUI 初始化 Controller 时就能自动获取
        target_table = table_name or config.TARGET_TABLE
        
        logger.info(f"🔧 [Controller] 初始化 | 目标数据库表: {target_table}")

        # 2. 初始化数据库
        self.db = DatabaseManager(config.DB_PATH, table_name=target_table)
        
        self.translator = TagTranslator(db_path=config.TAG_DB_PATH)
        
        # 3. 初始化去重管理器
        self.deduplicator = DeduplicationManager(self.db)
        
        self._is_running = False
        
        try:
            self.searcher = EHentaiHashSearcher(config.MY_COOKIES)
        except Exception as e:
            logger.error(f"初始化网络组件失败: {e}")
            self.searcher = None
            
        self.service = ScannerService(self.db, self.searcher, self.translator)

    # ... (后续方法保持不变) ...

    def _get_files_to_scan(self, directory: Path) -> List[Path]:
        """获取未扫描的文件"""
        if not directory.exists(): 
            logger.warning(f"❌ 目录不存在: {directory}")
            return []
        
        logger.info(f"📂 正在扫描目录: {directory} ...")

        all_files = set()
        extensions = ['*.zip', '*.rar', '*.7z', '*.cbz', '*.cbr']
        for ext in extensions:
            all_files.update(directory.rglob(ext))
        
        processed = self.db.get_all_processed_paths()
        
        pending = [f for f in all_files if str(f) not in processed]
        
        logger.info(f"📊 目录统计: 发现 {len(all_files)} 个 | 已入库 {len(processed)} | 🆕 待处理 {len(pending)}")
        return sorted(list(pending))

    def _get_files_to_retry(self) -> List[Path]:
        """从数据库获取失败项"""
        try:
            logger.info(f"🔍 正在查询表 [{self.db.table_name}] 中的失败记录...")
            cursor = self.db.conn.cursor() 
            cursor.execute(f"SELECT file_path FROM {self.db.table_name} WHERE status != 'SUCCESS'")
            rows = cursor.fetchall()
            
            files = []
            for row in rows:
                p = Path(row[0])
                if p.exists():
                    files.append(p)
            
            logger.info(f"📊 重试统计: 数据库记录 {len(rows)} 条 | 📁 实际文件存在 {len(files)} 个")
            return files
        except Exception as e:
            logger.error(f"❌ 获取重试列表失败: {e}")
            return []

    def scan_new_files(self, gui_callback=None):
        files = self._get_files_to_scan(Path(config.DEFAULT_DIR))
        self._run_batch(files, "新文件扫描", gui_callback, mode='cover')

    def retry_failures(self, gui_callback=None):
        files = self._get_files_to_retry()
        self._run_batch(files, "失败项智能重试", gui_callback, mode='second')

    def scan_failed_with_title(self, gui_callback=None):
        files = self._get_files_to_retry()
        self._run_batch(files, "失败项标题重扫", gui_callback, mode='title')
        
    def run_deduplication(self, gui_callback=None):
        """Action: 运行去重分析"""
        self._is_running = True
        msg = f"🔍 开始多维查重分析 (表: {self.db.table_name} -> {self.db.relations_table})..."
        logger.info(msg)
        self._log_ui(msg, gui_callback)
        
        try:
            count = self.deduplicator.run(progress_callback=gui_callback)
            msg = f"✅ 查重完成! 发现 {count} 个重复文件 (详情请查看 {self.db.relations_table} 表)"
            logger.info(msg)
            self._log_ui(msg, gui_callback)
            if gui_callback: gui_callback('done', msg)
        except Exception as e:
            err = f"❌ 查重出错: {e}"
            logger.error(err)
            if gui_callback: gui_callback('done', err)
        finally:
            self._is_running = False

    def stop_scanning(self):
        """外部调用此方法以终止扫描"""
        self._is_running = False
        print("🛑 接收到停止指令...")

    def _wait_interval(self):
        """智能休眠，防止请求过快"""
        min_sleep = getattr(config, 'SLEEP_MIN', 3.0)
        max_sleep = getattr(config, 'SLEEP_MAX', 5.0)
        
        sleep_time = random.uniform(min_sleep, max_sleep)
        
        step = 0.1 
        elapsed = 0
        while elapsed < sleep_time:
            if not self._is_running: return
            time.sleep(step)
            elapsed += step

    def _run_batch(self, files: List[Path], task_title: str, gui_callback=None, mode=None):
        """
        通用的批量处理循环
        """
        self._is_running = True
        total = len(files)
        current_mode = mode or config.DEFAULT_MODE
        
        start_msg = f"🚀 [任务启动] {task_title} | 模式: {current_mode} | 数量: {total}"
        logger.info(start_msg)
        self._log_ui(start_msg, gui_callback)

        if total == 0:
            if gui_callback: gui_callback('done', "完成 (无文件)")
            return

        success_count = 0
        is_stopped = False

        for i, file_path in enumerate(files, 1):
            if not self._is_running:
                logger.warning("🛑 用户停止任务")
                is_stopped = True
                break

            if i > 1:
                self._wait_interval()

            logger.info(f"▶️ 处理 [{i}/{total}]: {file_path.name}")
            
            try:
                result = self.service.process_file(file_path, mode=current_mode)
                if result.get('status') == 'SUCCESS':
                    success_count += 1
                
                status_text = f"{result.get('status')} | {result.get('file_name')}"
                if gui_callback:
                    gui_callback('progress', (i, total, status_text))
                    
            except Exception as e:
                logger.error(f"❌ 处理循环异常: {e}")

        final_msg = f"🏁 [{task_title}] 结束! 成功: {success_count}/{total}"
        if is_stopped:
            final_msg += " (用户终止)"
            
        logger.info(final_msg)
        self._log_ui(final_msg, gui_callback)
        
        if gui_callback:
            status_key = 'stopped' if is_stopped else 'done'
            gui_callback(status_key, final_msg)

    def _log_ui(self, msg, callback):
        if callback: callback('log', msg)