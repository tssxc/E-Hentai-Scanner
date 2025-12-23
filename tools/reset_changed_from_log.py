# tools/reset_changed_from_log.py
import re
import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config

def main():
    # 使用 rescan 的日志
    log_path = config.LOG_PATH_RESCAN
    
    if not os.path.exists(log_path):
        print("日志文件不存在")
        return

    changed_files = set()
    current_file = None
    file_pattern = re.compile(r"\[\d+/\d+\]\s+(.+\.(zip|rar|cbz))", re.IGNORECASE)
    change_pattern = re.compile(r"🔄 \[变更\] URL 发生变化")

    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            m = file_pattern.search(line)
            if m: current_file = m.group(1).strip()
            if change_pattern.search(line) and current_file:
                changed_files.add(current_file)

    if not changed_files:
        print("未发现变更项")
        return

    print(f"发现 {len(changed_files)} 个变更文件。准备重置...")
    if input("确认重置? (y/n): ").lower() != 'y': return

    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    # 默认为生产表，根据需要修改
    table = config.TABLE_PROD
    
    for f in changed_files:
        cursor.execute(f"UPDATE {table} SET gallery_url=NULL, status='RESET' WHERE file_name=?", (f,))
    
    conn.commit()
    conn.close()
    print("完成。")

if __name__ == "__main__":
    main()