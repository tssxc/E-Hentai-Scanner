# app/database.py
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
        # 1. 初始化主表
        sql_main = f"""
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
        self.cursor.execute(sql_main)

        # 2. 初始化临时分析表
        sql_dup = """
        CREATE TABLE IF NOT EXISTS url_duplicates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gallery_url TEXT,
            file_path TEXT,
            file_name TEXT,
            scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.cursor.execute(sql_dup)

        # 3. 初始化永久存档表
        sql_archive = """
        CREATE TABLE IF NOT EXISTS duplicates_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_file_path TEXT, 
            file_name TEXT,
            gallery_url TEXT,
            title TEXT,
            tags TEXT,
            moved_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.cursor.execute(sql_archive)
        self.conn.commit()

    # ==========================
    #  核心功能方法
    # ==========================

    def create_backup(self):
        """[修复] 创建数据库备份 (之前缺失的方法)"""
        if not self.db_path.exists():
            return

        try:
            self.conn.commit()
            shutil.copy2(self.db_path, self.backup_path)
            logger.info(f"💾 [Backup] 已创建备份: {self.backup_path.name}")
        except Exception as e:
            logger.error(f"❌ 创建备份失败: {e}")

    # [修复] 缩进调整：现在它是类的方法，而不是 create_backup 的内部函数
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
        """保存或更新记录"""
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
            # logger.debug(f"💾 [DB] 已保存: {file_name}")
        except Exception as e:
            logger.error(f"❌ [DB-Save] 写入失败: {e}")

    def get_record_by_path(self, file_path: Union[str, Path]) -> Optional[sqlite3.Row]:
        """根据路径获取记录 (Scanner 需要此方法)"""
        sql = f"SELECT * FROM {self.table_name} WHERE file_path = ?"
        try:
            self.cursor.execute(sql, (str(file_path),))
            return self.cursor.fetchone()
        except Exception:
            return None

    # ==========================
    #  重复检测与归档方法
    # ==========================

    def find_and_store_url_duplicates(self) -> int:
        """
        查找重复并存入临时表
        [修复] 强制重建表以包含 title 字段
        """
        try:
            # 1. 强制删除旧表 (关键步骤)
            self.cursor.execute("DROP TABLE IF EXISTS url_duplicates")
            
            # 2. 重新创建包含 title 的表
            sql_create = """
            CREATE TABLE url_duplicates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gallery_url TEXT,
                file_path TEXT,
                file_name TEXT,
                title TEXT,  -- 必须有这一列
                scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            self.cursor.execute(sql_create)
            
            # 3. 插入数据
            sql_insert = f"""
            INSERT INTO url_duplicates (gallery_url, file_path, file_name, title)
            SELECT gallery_url, file_path, file_name, title
            FROM {self.table_name}
            WHERE gallery_url IN (
                SELECT gallery_url
                FROM {self.table_name}
                WHERE status = 'SUCCESS' AND gallery_url IS NOT NULL AND gallery_url != ''
                GROUP BY gallery_url
                HAVING COUNT(*) > 1
            ) AND status = 'SUCCESS'
            ORDER BY gallery_url
            """
            
            self.cursor.execute(sql_insert)
            count = self.cursor.rowcount
            self.conn.commit()
            return count
        except Exception as e:
            logger.error(f"❌ 生成重复报告失败: {e}")
            return 0

    def archive_and_delete_record(self, file_path: str):
        """归档并从主表删除"""
        try:
            # 1. 查询
            self.cursor.execute(f"SELECT * FROM {self.table_name} WHERE file_path = ?", (file_path,))
            row = self.cursor.fetchone()
            
            if not row:
                return

            # 2. 归档
            moved_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sql_insert = """
            INSERT INTO duplicates_archive 
            (original_file_path, file_name, gallery_url, title, tags, moved_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            self.cursor.execute(sql_insert, (
                row['file_path'], row['file_name'], row['gallery_url'], 
                row['title'], row['tags'], moved_time
            ))

            # 3. 删除
            self.cursor.execute(f"DELETE FROM {self.table_name} WHERE file_path = ?", (file_path,))
            self.conn.commit()
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ [归档失败] {e}")
            raise e

    # ==========================
    #  通用方法
    # ==========================

    def get_all_processed_paths(self) -> Set[str]:
        try:
            self.cursor.execute(f"SELECT file_path FROM {self.table_name}")
            return {row['file_path'] for row in self.cursor.fetchall()}
        except Exception:
            return set()

    def get_statistics(self) -> Dict[str, int]:
        try:
            self.cursor.execute(f"SELECT status, COUNT(*) as count FROM {self.table_name} GROUP BY status")
            return {row['status']: row['count'] for row in self.cursor.fetchall()}
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