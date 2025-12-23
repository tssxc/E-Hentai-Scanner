import os
import sys
import shutil
import logging
import re
import sqlite3

# ================= 环境设置 =================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import config
from app.database import DatabaseManager

# ================= 路径配置 =================
# 请确保这里和 check_duplicates.py 一致
BASE_DEBUG_DIR = r"D:\漫画"
DUPLICATES_ROOT = os.path.join(BASE_DEBUG_DIR, "duplicates")

def get_original_filename(filename):
    """
    去除 check_duplicates.py 添加的时间戳前缀
    例如: 20251223120000_漫画名.zip -> 漫画名.zip
    """
    match = re.match(r'^\d{14}_(.+)$', filename)
    if match:
        return match.group(1)
    return filename

def restore_files(db):
    if not os.path.exists(DUPLICATES_ROOT):
        print(f"❌ 目录不存在: {DUPLICATES_ROOT}")
        return

    print(f"🚀 开始从 {DUPLICATES_ROOT} 还原...")
    print(f"📂 目标目录: {BASE_DEBUG_DIR} (不保留分类子文件夹)")
    
    success_count = 0
    fail_count = 0
    
    # 获取游标
    cursor = db.conn.cursor()

    # 遍历 duplicates 下的所有文件
    # os.walk 会进入所有子文件夹，但我们处理时会忽略子文件夹的路径，直接移到根目录
    for root, dirs, files in os.walk(DUPLICATES_ROOT):
        for file in files:
            # 1. 获取当前文件的绝对路径 (数据库里现在存的是这个)
            current_full_path = os.path.join(root, file)
            
            # 2. [核心修改] 目标路径直接设定为 漫画根目录
            # 我们不再使用 os.path.relpath 保留子目录结构
            # 这样文件就会从 duplicates/分类文件夹/文件.zip -> D:\漫画\文件.zip
            target_folder = BASE_DEBUG_DIR
            
            if not os.path.exists(target_folder):
                os.makedirs(target_folder)
            
            # 还原文件名 (去掉时间戳)
            original_name = get_original_filename(file)
            target_full_path = os.path.join(target_folder, original_name)
            
            # 防覆盖检查
            if os.path.exists(target_full_path):
                base, ext = os.path.splitext(original_name)
                # 如果根目录下已经有同名文件，添加后缀
                target_full_path = os.path.join(target_folder, f"{base}_restored{ext}")

            try:
                # =========================================
                # 核心步骤 A: 物理移动文件 (仅移动文件，不移动文件夹)
                # =========================================
                shutil.move(current_full_path, target_full_path)
                
                # =========================================
                # 核心步骤 B: 更新数据库 (不刮削，只改路)
                # =========================================
                # 只有当 WHERE file_path = current_full_path 匹配到记录时，才更新
                update_sql = f"UPDATE {db.table_name} SET file_path = ? WHERE file_path = ?"
                cursor.execute(update_sql, (target_full_path, current_full_path))
                
                if cursor.rowcount > 0:
                    print(f"✅ [完美还原] {original_name}")
                    success_count += 1
                else:
                    print(f"⚠️ [仅移动文件] 数据库中未找到记录: {file}")
                    fail_count += 1

                # 立即提交事务
                db.conn.commit()

            except Exception as e:
                print(f"❌ 错误: {e}")

    # =========================================
    # 步骤 C: 清理 duplicates 下剩下的空文件夹
    # =========================================
    print("🧹 正在清理空目录...")
    # topdown=False 确保先删除子目录再删除父目录
    for root, dirs, files in os.walk(DUPLICATES_ROOT, topdown=False):
        for name in dirs:
            dir_to_check = os.path.join(root, name)
            try:
                # 只有当文件夹为空时才删除
                if not os.listdir(dir_to_check):
                    os.rmdir(dir_to_check)
            except OSError:
                pass # 如果不为空（比如有移动失败的文件），则跳过
    
    # 最后尝试删除 duplicates 根目录
    try:
        if os.path.exists(DUPLICATES_ROOT) and not os.listdir(DUPLICATES_ROOT):
            os.rmdir(DUPLICATES_ROOT)
            print("🗑️  已清理 duplicates 根目录")
    except:
        pass

    print("-" * 30)
    print(f"🏁 还原完成")
    print(f"   🔹 完美还原 (保留元数据): {success_count}")
    print(f"   🔸 仅文件还原 (无元数据): {fail_count}")

if __name__ == "__main__":
    # 初始化数据库连接
    db = DatabaseManager(config.DB_PATH, table_name=config.TARGET_TABLE)
    try:
        restore_files(db)
    finally:
        db.close()