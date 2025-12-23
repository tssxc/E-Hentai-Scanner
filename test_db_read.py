# test_db_read.py
from app import config
import os
from app.database import DatabaseManager
from app.utils import calculate_similarity, parse_gallery_title

def test_dual_parsing_comparison():
    print(f"🔍 连接数据库: {config.DB_PATH}")
    print(f"📋 目标表: {config.TARGET_TABLE}")
    
    db = DatabaseManager(config.DB_PATH, config.TARGET_TABLE)
    
    try:
        # 随机抽取 5 条成功记录
        sql = f"SELECT * FROM {config.TARGET_TABLE} WHERE status='SUCCESS' ORDER BY RANDOM() LIMIT 5"
        db.cursor.execute(sql)
        rows = db.cursor.fetchall()
        
        if not rows:
            print("\n⚠️ 表中目前没有状态为 'SUCCESS' 的数据！")
            return

        print(f"\n⚖️  双向解析深度对比 (共 {len(rows)} 条):\n")
        
        for idx, row in enumerate(rows, 1):
            file_name = row['file_name']
            db_full_title = row['title']
            
            # === 1. 原始数据准备 ===
            # 本地文件名 (去后缀)
            local_raw = os.path.splitext(file_name)[0] 
            # 线上标题 (原样)
            online_raw = db_full_title

            # === 2. 双向解析 (核心逻辑) ===
            
            # A. 解析本地文件名
            # 假设本地文件也像 "[Circle] Title (Parody).zip" 这样命名
            local_parsed_info = parse_gallery_title(local_raw)
            local_core = local_parsed_info.get('title') if local_parsed_info.get('title') else local_raw
            
            # B. 解析线上标题
            online_parsed_info = parse_gallery_title(online_raw)
            online_core = online_parsed_info.get('title') if online_parsed_info.get('title') else online_raw

            # === 3. 计算分数 ===
            
            # 原始分: 含标签 vs 含标签
            score_origin = calculate_similarity(local_raw, online_raw)
            
            # 核心分: 纯标题 vs 纯标题
            score_core = calculate_similarity(local_core, online_core)
            
            # === 4. 差异展示 ===
            diff = score_core - score_origin
            if diff > 0.05:    change_icon = f"⬆️ +{diff:.2f}"
            elif diff < -0.05: change_icon = f"⬇️ {diff:.2f}"
            else:              change_icon = "➡️ 持平"

            # 评级
            if score_core > 0.8:   grade = "🟢 完美"
            elif score_core > 0.5: grade = "🟡 一般"
            elif score_core > 0.3: grade = "🟠 存疑"
            else:                  grade = "🔴 警告"

            print(f"=== Record #{idx} ===")
            print(f"📁 本地原名 : {local_raw}")
            print(f"✂️  本地核心 : {local_core}")
            print(f"----------------------------------------")
            print(f"📖 线上原名 : {online_raw}")
            print(f"✂️  线上核心 : {online_core}")
            print(f"----------------------------------------")
            print(f"📊 原始相似度 : {score_origin:.2f}")
            print(f"📊 核心相似度 : {score_core:.2f}  ({change_icon})  |  {grade}")
            print("=" * 50)

    except Exception as e:
        print(f"❌ 出错: {e}")
    finally:
        db.close()
        print("\n🔚 测试结束")

if __name__ == "__main__":
    test_dual_parsing_comparison()