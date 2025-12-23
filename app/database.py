# modules/database.py
import shutil
import sqlite3
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Set, Union

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: Union[str, Path], table_name: str = "scan_results"):
        self.db_path = Path(db_path)
        self.backup_path = self.db_path.with_suffix('.db.bak')
        self.table_name = table_name
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
        
        # 确保父目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._connect()

    def _connect(self):
        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self._init_table()
            logger.info(f"📂 数据库就绪 | 表: {self.table_name}")
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            raise e

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _init_table(self):
        sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE, 
            file_name TEXT,
            gallery_url TEXT,
            title TEXT,
            tags TEXT,
            status TEXT,
            scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.cursor.execute(sql)
        self.conn.commit()

    def create_backup(self):
        """创建数据库备份"""
        if not self.db_path.exists():
            logger.warning("⚠️ 数据库文件不存在，跳过备份")
            return

        try:
            self.conn.commit()
            shutil.copy2(self.db_path, self.backup_path)
            logger.info(f"💾 [Backup] 已创建备份: {self.backup_path.name}")
        except Exception as e:
            logger.error(f"❌ 创建备份失败: {e}")

    def rollback_to_backup(self) -> bool:
        """从备份恢复数据库"""
        self.close()

        if not self.backup_path.exists():
            logger.error("❌ 备份文件不存在，无法回溯！")
            return False

        try:
            if self.db_path.exists():
                os.remove(self.db_path)
            shutil.copy2(self.backup_path, self.db_path)
            logger.warning(f"🔙 [Rollback] 数据库已回溯！")
            # 重新连接
            self._connect()
            return True
        except Exception as e:
            logger.error(f"❌ 回溯失败: {e}")
            return False

    def save_record(self, file_path: Union[str, Path], status: str, 
                   url: Optional[str] = None, title: Optional[str] = None, 
                   tags: Optional[str] = None):
        file_path_str = str(file_path)
        file_name = Path(file_path).name
        scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        sql = f"""
        INSERT OR REPLACE INTO {self.table_name} 
        (file_path, file_name, gallery_url, title, tags, status, scan_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            self.cursor.execute(sql, (file_path_str, file_name, url, title, tags, status, scan_time))
            self.conn.commit()
            logger.debug(f"💾 [DB] 已保存: {file_name}")
        except Exception as e:
            logger.error(f"❌ [DB-Save] 写入失败: {e}")

    def get_record_by_path(self, file_path: Union[str, Path]) -> Optional[sqlite3.Row]:
        sql = f"SELECT * FROM {self.table_name} WHERE file_path = ?"
        try:
            self.cursor.execute(sql, (str(file_path),))
            return self.cursor.fetchone()
        except Exception:
            return None

    def get_all_processed_paths(self) -> Set[str]:
        try:
            self.cursor.execute(f"SELECT file_path FROM {self.table_name}")
            return {row['file_path'] for row in self.cursor.fetchall()}
        except Exception:
            return set()

    def get_statistics(self) -> Dict[str, int]:
        try:
            self.cursor.execute(f"SELECT status, COUNT(*) as count FROM {self.table_name} GROUP BY status")
            stats = {row['status']: row['count'] for row in self.cursor.fetchall()}
            logger.info(f"📊 [DB-Stats] 统计: {stats}")
            return stats
        except Exception:
            return {}

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            self.cursor = None

    def clear_current_table(self):
        """清空当前表 (仅测试模式)"""
        if "test" not in self.table_name.lower():
            logger.warning(f"⚠️ [DB-Safe] 拒绝清空非测试表: '{self.table_name}'")
            return

        try:
            self.cursor.execute(f"DELETE FROM {self.table_name}")
            self.cursor.execute("DELETE FROM sqlite_sequence WHERE name=?", (self.table_name,))
            self.conn.commit()
            logger.warning(f"🧹 [DB-Clean] 已清空测试表: {self.table_name}")
        except Exception as e:
            logger.error(f"❌ 清空表失败: {e}")
