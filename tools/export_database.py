# tools/export_database.py
"""
数据库导出工具
将扫描结果数据库导出为 JSON 和 CSV 格式，方便查看和分析
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


def export_database():
    logger.info("🚀 开始导出数据库...")
    
    try:
        # 初始化组件获取数据库连接
        db, _, _, _, _, _, _ = initialize_components()
        table_name = db.table_name
        
        # 获取所有数据
        cursor = db.conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        if not rows:
            logger.warning("⚠️ 数据库为空，没有任何记录。")
            return

        # 获取列名
        columns = [description[0] for description in cursor.description]
        
        # 转换数据为字典列表
        data_list = []
        for row in rows:
            data_list.append(dict(row))

        # ================= 1. 导出为 JSON =================
        json_file = os.path.join(project_root, "data", "export_scan_results.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2, default=custom_serializer)
        logger.info(f"✅ [JSON] 已导出: {json_file}")

        # ================= 2. 导出为 CSV (Excel可用) =================
        csv_file = os.path.join(project_root, "data", "export_scan_results.csv")
        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data_list)
        logger.info(f"✅ [CSV ] 已导出: {csv_file}")

        logger.info(f"🎉 导出完成！共 {len(data_list)} 条记录。")

    except Exception as e:
        logger.error(f"❌ 导出失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db' in locals():
            db.close()


if __name__ == "__main__":
    export_database()

