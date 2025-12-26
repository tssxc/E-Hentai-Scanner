# tools/check_duplicates.py
import os
import sys
import shutil
import logging
import re
import difflib
from collections import defaultdict, deque
from datetime import datetime

# ================= 环境设置 =================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import config
from app.database import DatabaseManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ================= 路径配置 =================

# 注意：请确保这里的路径与您的实际漫画路径一致，或者修改为从 config 读取
BASE_DEBUG_DIR = r"D:\漫画"
DUPLICATES_ROOT = os.path.join(BASE_DEBUG_DIR, "duplicates")

# ================= 辅助函数 =================

def ensure_duplicates_root():
    if not os.path.exists(DUPLICATES_ROOT):
        print(f"📁 创建目录: {DUPLICATES_ROOT}")
        os.makedirs(DUPLICATES_ROOT)
    else:
        print(f"📂 重复文件库: {DUPLICATES_ROOT}")

def sanitize_filename(name):
    """
    [关键修复] 清理文件名
    1. 移除非法字符
    2. 移除 Windows 不允许的末尾点(.)和空格
    """
    if not name: return "Unknown_Title"
    
    # 移除括号内容
    name = re.sub(r'[\[\(\{].*?[\]\)\}]', '', name) 
    
    # 将非法字符替换为空格
    clean = re.sub(r'[\\/*?:"<>|]', ' ', name)
    
    # [关键修复]: .strip(" .") 会同时移除开头和结尾的 空格 和 点
    # Windows 文件夹严禁以点结尾
    clean = clean.strip(" .")
    
    # 合并多余空格
    clean = ' '.join(clean.split())
    
    if not clean:
        return "Unknown_Title"
        
    return clean[:100]

def clean_title_for_comparison(title):
    if not title: return ""
    t = title.lower()
    t = re.sub(r'[\[\(\{].*?[\]\)\}]', '', t)
    t = re.sub(r'\.(zip|rar|cbz|cbr|7z)$', '', t)
    t = re.sub(r'[._\-,|]', ' ', t)
    return ' '.join(t.split())

def resolve_target_folder(base_title):
    """智能文件夹匹配：如果 duplicates 下存在相似文件夹，则复用"""
    proposed_name = sanitize_filename(base_title)
    if not proposed_name: proposed_name = "Unknown_Folder"
    
    if not os.path.exists(DUPLICATES_ROOT):
        return proposed_name

    existing_dirs = [d for d in os.listdir(DUPLICATES_ROOT) 
                     if os.path.isdir(os.path.join(DUPLICATES_ROOT, d))]
    
    proposed_clean = clean_title_for_comparison(proposed_name)
    best_match = None
    highest_ratio = 0.0

    for existing_dir in existing_dirs:
        if existing_dir == proposed_name: return existing_dir
        existing_clean = clean_title_for_comparison(existing_dir)
        ratio = difflib.SequenceMatcher(None, proposed_clean, existing_clean).ratio()
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = existing_dir

    if highest_ratio > 0.90 and best_match:
        return best_match
    
    return proposed_name

def is_safe_duplicate(title_a, title_b, ratio, threshold=0.90):
    if ratio < threshold: return False
    nums_a = re.findall(r'\d+', title_a)
    nums_b = re.findall(r'\d+', title_b)
    if nums_a != nums_b: return False
    return True

def move_file_and_archive(file_path, db, sub_folder_name):
    """
    [修改版] 执行物理移动，并更新数据库路径 (而不是删除记录)
    """
    try:
        # 1. 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"   ⚠️ 文件未找到: {file_path}")
            # 如果文件本身不存在，可以选择清理死链，或者跳过
            # db.archive_and_delete_record(file_path) 
            return False
            
        # 2. 准备目标路径
        target_dir = os.path.join(DUPLICATES_ROOT, sub_folder_name)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        file_name = os.path.basename(file_path)
        name_part, ext_part = os.path.splitext(file_name)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # 3. 防冲突命名
        new_name = f"{timestamp}_{file_name}"
        dest_path = os.path.join(target_dir, new_name)
        
        counter = 1
        while os.path.exists(dest_path):
            new_name = f"{timestamp}_{name_part}_{counter}{ext_part}"
            dest_path = os.path.join(target_dir, new_name)
            counter += 1
        
        # 4. 物理移动文件
        real_dest_path = shutil.move(file_path, dest_path)
        
        # 5. [核心修改] 更新数据库路径
        # 不再删除记录，而是将 file_path 更新为 duplicates 下的新路径
        cursor = db.conn.cursor()
        update_sql = f"UPDATE {db.table_name} SET file_path = ? WHERE file_path = ?"
        cursor.execute(update_sql, (real_dest_path, file_path))
        db.conn.commit()
        
        print(f"   🔄 [已移动+更新DB] ...{file_name[-15:]} -> {sub_folder_name}")
        return True

    except Exception as e:
        print(f"   ❌ 移动/更新失败: {e}")
        return False

# ================= 阶段 1: 数据收集 =================

def collect_url_groups(db):
    print("   🔍 [1/3] 扫描 URL 重复...")
    count = db.find_and_store_url_duplicates() # 这一步会填充 url_duplicates 表
    if count == 0:
        return []
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT * FROM url_duplicates")
    records = cursor.fetchall()
    
    # 转换为字典: {url: [row1, row2...]}
    groups_map = defaultdict(list)
    for row in records:
        groups_map[row['gallery_url']].append(row)
    
    return list(groups_map.values())

def collect_title_groups(db):
    print("   🔍 [2/3] 扫描 标题 相似 (这可能需要一点时间)...")
    cursor = db.conn.cursor()
    cursor.execute(f"SELECT * FROM {db.table_name} WHERE status='SUCCESS'")
    all_records = cursor.fetchall()
    
    if not all_records: return []

    # 预处理
    data_list = []
    for row in all_records:
        raw_title = row['title'] if row['title'] else row['file_name']
        cleaned = clean_title_for_comparison(raw_title)
        data_list.append({
            'row': row,
            'clean_title': cleaned
        })
    
    data_list.sort(key=lambda x: x['clean_title'])
    
    title_groups = []
    total = len(data_list)
    processed_indices = set()
    window_size = 10
    
    for i in range(total):
        if i in processed_indices: continue
        
        item_a = data_list[i]
        current_group = [item_a['row']]
        has_match = False
        
        for j in range(i + 1, min(i + 1 + window_size, total)):
            if j in processed_indices: continue
            
            item_b = data_list[j]
            ratio = difflib.SequenceMatcher(None, item_a['clean_title'], item_b['clean_title']).ratio()
            
            if is_safe_duplicate(item_a['clean_title'], item_b['clean_title'], ratio):
                current_group.append(item_b['row'])
                processed_indices.add(j)
                has_match = True
        
        if has_match:
            processed_indices.add(i)
            title_groups.append(current_group)
            
    return title_groups

# ================= 阶段 2: 结果合并 (核心逻辑) =================

def merge_and_execute(db):
    print("\n🚀 [E-Hentai Scanner] 综合去重模式启动 (全部转移模式)")
    ensure_duplicates_root()

    # --- 1. 获取两组数据 ---
    url_groups = collect_url_groups(db)
    print(f"    ✅ URL 组数: {len(url_groups)}")
    
    title_groups = collect_title_groups(db)
    print(f"    ✅ 标题 组数: {len(title_groups)}")

    if not url_groups and not title_groups:
        print("🎉 没有发现任何重复文件。")
        return

    print("   🔗 [3/3] 正在合并检测结果并生成连通图...")

    # --- 2. 构建图 (Adjacency List) ---
    adj = defaultdict(set)
    file_info_map = {} 

    def add_clique_to_graph(group_rows):
        paths = [r['file_path'] for r in group_rows]
        for r in group_rows:
            file_info_map[r['file_path']] = r
            
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                u, v = paths[i], paths[j]
                adj[u].add(v)
                adj[v].add(u)

    for group in url_groups:
        add_clique_to_graph(group)
        
    for group in title_groups:
        add_clique_to_graph(group)

    # --- 3. 寻找连通分量 (BFS) ---
    visited = set()
    final_clusters = []

    all_nodes = list(file_info_map.keys())
    
    for start_node in all_nodes:
        if start_node in visited:
            continue
            
        cluster = []
        queue = deque([start_node])
        visited.add(start_node)
        
        while queue:
            node = queue.popleft()
            cluster.append(file_info_map[node])
            
            for neighbor in adj[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        if len(cluster) > 1:
            final_clusters.append(cluster)

    print(f"    ✅ 最终合并为 {len(final_clusters)} 个处理组。")
    print("-" * 50)

    # --- 4. 执行移动 ---
    total_moved = 0
    
    for idx, cluster in enumerate(final_clusters, 1):
        cluster_with_size = []
        for row in cluster:
            size = 0
            if os.path.exists(row['file_path']):
                size = os.path.getsize(row['file_path'])
            cluster_with_size.append((size, row))
        
        # 按大小降序排序 (仅用于确定文件夹命名的基准，即最大的那个)
        cluster_with_size.sort(key=lambda x: x[0], reverse=True)
        
        # 4.1 获取信息用于命名 (依然使用最大的文件来决定文件夹名)
        first_size, first_row = cluster_with_size[0]
        
        # 4.2 确定要移动的文件 (改为：全部移动)
        to_move_list = cluster_with_size
        
        raw_title = first_row['title'] if first_row['title'] else first_row['file_name']
        folder_name = resolve_target_folder(raw_title)
        
        print(f"[{idx}/{len(final_clusters)}] 📦 处理组 -> {folder_name} (包含 {len(to_move_list)} 个文件)")
        
        # 4.3 执行移动
        for _, row in to_move_list:
            if move_file_and_archive(row['file_path'], db, folder_name):
                total_moved += 1

    print("-" * 50)
    print(f"🏁 全部完成! 共移动 {total_moved} 个文件 (所有重复组均已移入 duplicates)。")

# ================= 主程序 =================

def main():
    db = DatabaseManager(config.DB_PATH, table_name=config.TARGET_TABLE)
    try:
        merge_and_execute(db)
    except KeyboardInterrupt:
        print("\n🛑 用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()