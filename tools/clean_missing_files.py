import sys
import sqlite3
import logging
from pathlib import Path

# 1. 将项目根目录加入路径，确保能导入 app 配置
project_root = Path(__file__).resolve().parent.parent
# 如果脚本直接放在根目录，请使用: project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from app import config

# 2. 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("Cleaner")

def clean_missing_files():
    """
    检查数据库记录，如果对应的文件在磁盘上不存在，则删除该数据库记录。
    """
    db_path = config.DB_PATH
    
    # 获取当前配置的表名 (会根据 config.IS_DEBUG_MODE 自动切换)
    table_name = config.TARGET_TABLE

    if not db_path.exists():
        logger.error(f"❌ 数据库文件未找到: {db_path}")
        return

    logger.info(f"📂 数据库路径: {db_path}")
    logger.info(f"📋 操作表名: {table_name}")
    logger.info("-" * 30)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    missing_records = [] # 存储 (id, file_path)
    
    try:
        # 1. 查询所有记录
        # 假设表结构中有 id 和 file_path 字段
        cursor.execute(f"SELECT id, file_path FROM {table_name}")
        rows = cursor.fetchall()
        
        logger.info(f"🔍 正在检查 {len(rows)} 条记录...")

        # 2. 遍历检查文件是否存在
        for row_id, file_path_str in rows:
            if not file_path_str:
                continue
                
            file_path = Path(file_path_str)
            if not file_path.exists():
                logger.warning(f"❌ 文件已丢失: {file_path}")
                missing_records.append((row_id, file_path_str))

        # 3. 如果没有发现丢失文件
        if not missing_records:
            logger.info("✨ 完美！所有数据库记录对应的文件都存在，无需清理。")
            return

        # 4. 确认删除
        logger.info("-" * 30)
        logger.info(f"⚠️ 共发现 {len(missing_records)} 条无效记录。")
        confirm = input("🔥 是否从数据库中删除这些记录？(y/n): ").strip().lower()
        
        if confirm == 'y':
            # 5. 执行批量删除
            ids_to_delete = [(r[0],) for r in missing_records]
            cursor.executemany(f"DELETE FROM {table_name} WHERE id = ?", ids_to_delete)
            conn.commit()
            logger.info(f"✅ 成功删除 {cursor.rowcount} 条记录！")
        else:
            logger.info("🚫 操作已取消，数据库未变更。")

    except sqlite3.OperationalError as e:
        logger.error(f"❌ 数据库操作错误 (可能是表名不对): {e}")
    except Exception as e:
        logger.error(f"❌ 发生意外错误: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    clean_missing_files()