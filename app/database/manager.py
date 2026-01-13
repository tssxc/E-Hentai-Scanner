# app/database/manager.py
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, Union, List, Dict
import sqlite3

from .core import DatabaseCore

logger = logging.getLogger(__name__)

class DatabaseManager(DatabaseCore):
    """
    具体业务数据库管理器
    """
    def __init__(self, db_path: Union[str, Path], table_name: str = "scan_results"):
        super().__init__(db_path)
        self.table_name = table_name
        
        # [动态生成查重相关表名]
        # 这样当 table_name="test_results" 时，会自动使用 "test_results_groups"
        self.groups_table = f"{table_name}_groups"
        self.relations_table = f"{table_name}_relations"
        
        self._init_schema()
        self._check_schema_migration()
        logger.info(f"📂 数据库就绪 | 主表: {self.table_name} | 查重表: {self.groups_table}, {self.relations_table}")

    def _init_schema(self):
        """初始化具体的业务表结构和索引"""
        ddl_statements = [
            # 1. 主数据表
            f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE, 
                file_name TEXT,
                gallery_url TEXT,
                title TEXT,
                tags TEXT,
                status TEXT,
                note TEXT,
                scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_url ON {self.table_name}(gallery_url)",
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_path ON {self.table_name}(file_path)",
            
            # 2. 查重组表 (Group) - 使用动态表名
            f"""
            CREATE TABLE IF NOT EXISTS {self.groups_table} (
                group_id TEXT PRIMARY KEY,
                duplicate_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # 3. 查重关系表 (Relation) - 使用动态表名
            f"""
            CREATE TABLE IF NOT EXISTS {self.relations_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT,
                file_path TEXT,
                file_name TEXT,
                similarity_score REAL,
                is_ref INTEGER DEFAULT 0,
                FOREIGN KEY(group_id) REFERENCES {self.groups_table}(group_id)
            )
            """,
            # 动态索引名
            f"CREATE INDEX IF NOT EXISTS idx_{self.relations_table}_group ON {self.relations_table}(group_id)",
            f"CREATE INDEX IF NOT EXISTS idx_{self.relations_table}_file ON {self.relations_table}(file_path)"
        ]

        with self._lock:
            try:
                cursor = self.conn.cursor()
                for sql in ddl_statements:
                    cursor.execute(sql)
                self.conn.commit()
            except Exception as e:
                logger.error(f"❌ 初始化 Schema 失败: {e}")

    def _check_schema_migration(self):
        """检查并自动修复表结构"""
        with self._lock:
            try:
                self.conn.execute(f"SELECT note FROM {self.table_name} LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    self.conn.execute(f"ALTER TABLE {self.table_name} ADD COLUMN note TEXT")
                    self.conn.commit()
                except Exception: pass

    # ================= 业务方法 =================

    def save_record(self, file_path: Union[str, Path], status: str, 
                    url: Optional[str] = None, title: Optional[str] = None, 
                    tags: Optional[str] = None, note: Optional[str] = None):
        sql = f"""
        INSERT OR REPLACE INTO {self.table_name} 
        (file_path, file_name, gallery_url, title, tags, status, note, scan_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            str(file_path), Path(file_path).name, url, title, tags, status, note,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        self._execute_write(sql, params)

    def get_record_by_path(self, file_path: Union[str, Path]) -> Optional[sqlite3.Row]:
        sql = f"SELECT * FROM {self.table_name} WHERE file_path = ?"
        return self._execute_read(sql, (str(file_path),), fetch_one=True)

    def get_all_processed_paths(self) -> Set[str]:
        sql = f"SELECT file_path FROM {self.table_name}"
        rows = self._execute_read(sql)
        return {row['file_path'] for row in rows} if rows else set()

    def get_success_records(self) -> List[Dict]:
        """获取所有 status='SUCCESS' 的记录"""
        sql = f"""
        SELECT id, file_path, file_name, gallery_url, title 
        FROM {self.table_name} 
        WHERE status = 'SUCCESS'
        """
        rows = self._execute_read(sql)
        return [dict(row) for row in rows] if rows else []

    def find_and_store_url_duplicates(self) -> int:
        return 0
            
    def store_dedup_results(self, flat_records: List[Dict]):
        """
        批量存储高级查重结果到关系表
        """
        if not flat_records: return

        try:
            with self._lock:
                # 1. 清空旧表 (使用动态表名)
                self.conn.execute(f"DELETE FROM {self.relations_table}")
                self.conn.execute(f"DELETE FROM {self.groups_table}")
                
                # 2. 插入数据
                groups_map = {}
                relations_data = []

                for item in flat_records:
                    gid = item['group_id']
                    if gid not in groups_map:
                        groups_map[gid] = item['type']
                    
                    relations_data.append((
                        gid,
                        item['file_path'],
                        item['file_name'],
                        item.get('score', 0.0)
                    ))

                # 3. 批量插入组表
                sql_group = f"""
                INSERT INTO {self.groups_table} (group_id, duplicate_type) 
                VALUES (?, ?)
                """
                self.conn.executemany(sql_group, list(groups_map.items()))

                # 4. 批量插入关系表
                sql_rel = f"""
                INSERT INTO {self.relations_table} 
                (group_id, file_path, file_name, similarity_score)
                VALUES (?, ?, ?, ?)
                """
                self.conn.executemany(sql_rel, relations_data)

                self.conn.commit()
                logger.info(f"💾 查重数据已保存到 [{self.relations_table}] ({len(groups_map)} 组)")
                
        except Exception as e:
            logger.error(f"❌ 存储查重结果失败: {e}")