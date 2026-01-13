# app/database/core.py
import sqlite3
import logging
import threading
import shutil
from pathlib import Path
from typing import Optional, Union, Tuple, Any

logger = logging.getLogger(__name__)

class DatabaseCore:
    """
    数据库核心基类
    负责：连接管理、WAL配置、线程锁、通用SQL执行、物理备份
    """
    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)
        self.backup_path = self.db_path.with_suffix('.db.bak')
        self.conn: Optional[sqlite3.Connection] = None
        
        # 线程锁：虽然 WAL 模式支持并发读，但写操作仍需串行化
        self._lock = threading.Lock()
        
        # 确保存储目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connect()

    def _connect(self):
        """建立数据库连接并应用优化配置"""
        try:
            # check_same_thread=False: 允许在不同线程使用同一个连接对象
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            
            # [优化] 开启 WAL 模式 (Write-Ahead Logging)
            self.conn.execute("PRAGMA journal_mode=WAL;")
            
            # 使用 Row 工厂，使查询结果可以通过列名访问 (row['field'])
            self.conn.row_factory = sqlite3.Row
            
            logger.debug(f"🔌 数据库连接建立 (WAL Mode): {self.db_path.name}")
            
        except Exception as e:
            logger.critical(f"❌ 数据库连接失败: {e}")
            raise e

    def _execute_write(self, sql: str, params: Tuple = ()) -> bool:
        """通用写操作：加锁 -> 执行 -> 提交 -> 捕获异常"""
        try:
            with self._lock:
                self.conn.execute(sql, params)
                self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ [DB-Write] 执行失败: {e}\nSQL: {sql}\nParams: {params}")
            return False

    def _execute_read(self, sql: str, params: Tuple = (), fetch_one: bool = False) -> Any:
        """通用读操作：加锁 -> 执行 -> 返回结果"""
        try:
            with self._lock:
                cursor = self.conn.execute(sql, params)
                return cursor.fetchone() if fetch_one else cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ [DB-Read] 查询失败: {e}")
            return None if fetch_one else []

    def create_backup(self):
        """创建数据库物理备份"""
        if not self.db_path.exists(): return
        try:
            with self._lock:
                self.conn.commit() # 确保内存数据落盘
                shutil.copy2(self.db_path, self.backup_path)
                logger.info(f"💾 [Backup] 备份成功: {self.backup_path.name}")
        except Exception as e:
            logger.error(f"❌ 备份失败: {e}")

    def close(self):
        """关闭连接"""
        if self.conn:
            try:
                self.conn.close()
                logger.debug("🔒 数据库连接已关闭")
            except Exception: pass
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()