import os
import sys
import logging

# ================= 环境设置 =================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import config
from app.database import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(message)s')

def reset_tables():
    print("🧨 [工具] 数据库表重置工具")
    
    db = DatabaseManager(config.DB_PATH, table_name=config.TARGET_TABLE)
    
    try:
        # 1. 删除 url_duplicates (临时表)
        # 删除这个表可以解决 "No item with that key" 错误，让程序下次运行时重新创建正确的表结构
        print("1. 正在删除 'url_duplicates' 表...")
        db.cursor.execute("DROP TABLE IF EXISTS url_duplicates")
        
        # 2. (可选) 删除 duplicates_archive (归档表)
        # 如果您想清空之前的归档历史，可以取消下面几行的注释
        # print("2. 正在删除 'duplicates_archive' 表...")
        # db.cursor.execute("DROP TABLE IF EXISTS duplicates_archive")
        
        db.conn.commit()
        print("✅ 删除成功！下次运行检查工具时，表将会自动重建。")
        
    except Exception as e:
        print(f"❌ 删除失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_tables()