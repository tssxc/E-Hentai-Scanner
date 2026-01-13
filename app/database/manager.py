# app/database/manager.py
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, Union
import sqlite3

from .core import DatabaseCore

logger = logging.getLogger(__name__)

class DatabaseManager(DatabaseCore):
    """
    具体业务数据库管理器
    负责：表结构定义(Schema)、具体的 CRUD 操作
    """
    def __init__(self, db_path: Union[str, Path], table_name: str = "scan_results"):
        super().__init__(db_path)
        self.table_name = table_name
        self._init_schema()
        self._check_schema_migration() # [新增] 检查并自动修复表结构(添加缺少列)
        logger.info(f"📂 数据库就绪 | 表: {self.table_name}")

    def _init_schema(self):
        """初始化具体的业务表结构和索引"""
        ddl_statements = [
            # 1. 主表
            f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE, 
                file_name TEXT,
                gallery_url TEXT,
                title TEXT,
                tags TEXT,
                status TEXT,
                note TEXT,  -- [新增] 备注字段
                scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # 2. 索引
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_url ON {self.table_name}(gallery_url)",
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_path ON {self.table_name}(file_path)",
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_status ON {self.table_name}(status)",
            # 3. 归档表
            """
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
        ]

        # 直接调用父类的 conn 执行初始化
        with self._lock:
            try:
                cursor = self.conn.cursor()
                for sql in ddl_statements:
                    cursor.execute(sql)
                self.conn.commit()
            except Exception as e:
                logger.error(f"❌ 初始化 Schema 失败: {e}")

    def _check_schema_migration(self):
        """
        [新增] 数据库迁移逻辑
        检查现有表中是否有 note 字段，如果没有则自动添加。
        """
        with self._lock:
            try:
                # 尝试查询 note 列，看看是否存在
                self.conn.execute(f"SELECT note FROM {self.table_name} LIMIT 1")
            except sqlite3.OperationalError:
                # 如果报错说明列不存在，执行添加列操作
                logger.warning(f"⚠️ 检测到旧版数据库表 {self.table_name}，正在自动添加 'note' 字段...")
                try:
                    self.conn.execute(f"ALTER TABLE {self.table_name} ADD COLUMN note TEXT")
                    self.conn.commit()
                    logger.info("✅ 数据库结构升级完成")
                except Exception as e:
                    logger.error(f"❌ 数据库升级失败: {e}")

    # ================= 业务方法 =================

    # [修改] 增加 note 参数
    def save_record(self, file_path: Union[str, Path], status: str, 
                    url: Optional[str] = None, title: Optional[str] = None, 
                    tags: Optional[str] = None, note: Optional[str] = None):
        """保存或更新扫描记录"""
        
        # [修改] SQL 插入语句增加 note 字段
        sql = f"""
        INSERT OR REPLACE INTO {self.table_name} 
        (file_path, file_name, gallery_url, title, tags, status, note, scan_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            str(file_path), 
            Path(file_path).name, 
            url, 
            title, 
            tags, 
            status,
            note,  # [新增] 传入 note 参数
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        self._execute_write(sql, params)

    def get_record_by_path(self, file_path: Union[str, Path]) -> Optional[sqlite3.Row]:
        """根据路径获取单条记录"""
        sql = f"SELECT * FROM {self.table_name} WHERE file_path = ?"
        return self._execute_read(sql, (str(file_path),), fetch_one=True)

    def get_all_processed_paths(self) -> Set[str]:
        """获取所有已入库的文件路径"""
        sql = f"SELECT file_path FROM {self.table_name}"
        rows = self._execute_read(sql)
        return {row['file_path'] for row in rows} if rows else set()

    def find_and_store_url_duplicates(self) -> int:
        """复杂业务：分析重复并生成报告"""
        try:
            with self._lock:
                self.conn.execute("DROP TABLE IF EXISTS url_duplicates")
                self.conn.execute("""
                CREATE TABLE url_duplicates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gallery_url TEXT,
                    file_path TEXT,
                    file_name TEXT,
                    title TEXT,
                    scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                sql_analyze = f"""
                INSERT INTO url_duplicates (gallery_url, file_path, file_name, title)
                SELECT t1.gallery_url, t1.file_path, t1.file_name, t1.title
                FROM {self.table_name} t1
                INNER JOIN (
                    SELECT gallery_url
                    FROM {self.table_name}
                    WHERE status = 'SUCCESS' 
                      AND gallery_url IS NOT NULL 
                      AND gallery_url != ''
                    GROUP BY gallery_url
                    HAVING COUNT(*) > 1
                ) t2 ON t1.gallery_url = t2.gallery_url
                ORDER BY t1.gallery_url
                """
                
                cursor = self.conn.execute(sql_analyze)
                count = cursor.rowcount
                self.conn.commit()
                return count
        except Exception as e:
            logger.error(f"❌ 生成去重报告失败: {e}")
            if self.conn: self.conn.rollback()
            return 0