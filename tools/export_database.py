# tools/export_database.py
"""
数据库导出工具 (全量)
将数据库中所有的表导出为 JSON 和 CSV 格式，方便查看和分析
"""
import os
import sys
import json
import csv
import logging
import sqlite3
from datetime import datetime

# ================= 环境设置 =================
# 确保可以将项目根目录加入 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import config
from app.common import initialize_components

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def custom_serializer(obj):
    """JSON 序列化辅助函数，处理日期等特殊类型"""
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    return str(obj)


def export_single_table(cursor, table_name, output_dir):
    """
    导出单个表的数据
    """
    logger.info(f"📂 正在处理表: {table_name} ...")
    
    try:
        # 获取该表所有数据
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        if not rows:
            logger.warning(f"   ⚠️ 表 {table_name} 为空，跳过导出。")
            return

        # 获取列名
        columns = [description[0] for description in cursor.description]
        
        # 转换数据为字典列表
        data_list = []
        for row in rows:
            data_list.append(dict(row))

        # ================= 1. 导出为 JSON =================
        json_filename = f"export_{table_name}.json"
        json_file = os.path.join(output_dir, json_filename)
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2, default=custom_serializer)
        logger.info(f"   ✅ [JSON] 已导出: {json_filename}")

        # ================= 2. 导出为 CSV =================
        csv_filename = f"export_{table_name}.csv"
        csv_file = os.path.join(output_dir, csv_filename)
        
        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data_list)
        logger.info(f"   ✅ [CSV ] 已导出: {csv_filename}")

    except Exception as e:
        logger.error(f"   ❌ 表 {table_name} 导出失败: {e}")


def export_database():
    logger.info("🚀 开始导出数据库 (所有表)...")
    
    db = None
    try:
        # 初始化组件获取数据库连接
        # 注意：initialize_components 返回 6 个或 7 个值，这里只取第一个 db
        components = initialize_components()
        db = components[0]
        
        output_dir = os.path.join(project_root, "data")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        cursor = db.conn.cursor()

        # 1. 获取数据库中所有的表名
        # sqlite_master 存储了数据库的元数据
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            logger.warning("⚠️ 数据库中没有找到任何表。")
            return

        exported_count = 0
        
        # 2. 循环导出每个表
        for table_row in tables:
            table_name = table_row['name'] # 假设 row_factory 为 Row 或 dict，如果是元组则用 table_row[0]
            # 兼容处理：如果 row_factory 没设置，fetchall 返回的是元组
            if isinstance(table_row, tuple):
                table_name = table_row[0]

            # 跳过 SQLite 内部序列表
            if table_name == 'sqlite_sequence':
                continue

            export_single_table(cursor, table_name, output_dir)
            exported_count += 1

        logger.info(f"🎉 全部导出完成！共导出 {exported_count} 个表。")

    except Exception as e:
        logger.error(f"❌ 导出过程发生严重错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    export_database()