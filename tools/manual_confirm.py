# tools/manual_confirm.py
import os
import sys
import webbrowser
import logging

# ================= 环境设置 =================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import config
from app.common import initialize_components
from app.scanner_core import scan_single_file 
# 注意：即使跳过自动检测，仍建议保留 validator 用于获取格式化后的元数据

# 配置简单的日志输出
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def manual_confirm_all():
    print("🚀 [工具] 启动人工核对程序 (重扫后跳过自动校验，由人工判定)...")
    
    try:
        # 初始化组件
        db, searcher, translator, _, handler, _, _ = initialize_components()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return

    try:
        table_name = db.table_name
        cursor = db.conn.cursor()
        # 排除已成功的记录
        cursor.execute(f"SELECT * FROM {table_name} WHERE status NOT IN ('SUCCESS', 'NO_MATCH')")
        records = cursor.fetchall()
        
        if not records:
            print("✅ 数据库中没有需要处理的记录。")
            return

        total = len(records)
        for idx, row in enumerate(records, 1):
            file_path = row['file_path']
            file_name = row['file_name']
            gallery_url = row['gallery_url']
            title = row['title']
            tags = row['tags']
            status = row['status']
            
            file_exists = os.path.exists(file_path)

            print("\n" + "="*60)
            print(f"[{idx}/{total}] 待处理: {file_name} | 状态: {status}")
            print("="*60)
            
            processed = False
            while not processed:
                print(f"🔗 当前标题: {title if title else '(无)'}")
                print(f"🌐 当前 URL: {gallery_url if gallery_url else '(无)'}")
                print("-" * 60)
                # [修改] 添加了 [s]重扫第二页 选项
                print("👉 操作选项: [y]确认当前 [c]重扫封面 [s]重扫第二页 [o]打开网页 [n]跳过 [f]标记失败 [q]退出")
                
                choice = input("请输入指令: ").lower().strip()
                
                if choice in ['y', 'yes']:
                    if not gallery_url:
                        print("❌ 错误: 当前没有有效 URL")
                        continue
                    db.save_record(file_path, "SUCCESS", gallery_url, title, tags)
                    print("✅ 已确认为: SUCCESS")
                    processed = True

                # === 封面扫描逻辑 ===
                elif choice in ['c', 'cover']:
                    if not file_exists:
                        print("❌ 文件不存在，无法扫描。")
                        continue
                        
                    print("🔄 正在执行封面扫描...")
                    try:
                        result = scan_single_file(file_path, searcher, handler, scan_mode='cover')
                        
                        if result['success'] and result.get('url'):
                            new_url = result.get('url')
                            new_title = result.get('title', 'Unknown Title')
                            new_tags = result.get('tags', '')
                            
                            print(f"✨ [重扫成功] 发现相关画廊:")
                            print(f"   标题: {new_title}")
                            print(f"   URL : {new_url}")
                            
                            confirm = input("👉 是否采纳此结果并标记为 SUCCESS? (y/n): ").lower().strip()
                            if confirm == 'y':
                                db.save_record(file_path, "SUCCESS", new_url, new_title, new_tags)
                                print("✅ 数据库已更新为 SUCCESS")
                                processed = True 
                            else:
                                gallery_url, title, tags = new_url, new_title, new_tags
                                print("   结果已暂存，您可以继续操作或打开网页确认。")
                        else:
                            print(f"❌ [扫描无结果] {result.get('message')}")
                    except Exception as e:
                        print(f"❌ 扫描过程出错: {e}")

                # === [新增] 第二页扫描逻辑 ===
                elif choice in ['s', 'second']:
                    if not file_exists:
                        print("❌ 文件不存在，无法扫描。")
                        continue
                        
                    print("🔄 正在执行第二页扫描...")
                    try:
                        # [关键修改] 调用 scan_single_file 并传入 scan_mode='second'
                        result = scan_single_file(file_path, searcher, handler, scan_mode='second')
                        
                        if result['success'] and result.get('url'):
                            new_url = result.get('url')
                            new_title = result.get('title', 'Unknown Title')
                            new_tags = result.get('tags', '')
                            
                            print(f"✨ [重扫成功] 发现相关画廊:")
                            print(f"   标题: {new_title}")
                            print(f"   URL : {new_url}")
                            
                            confirm = input("👉 是否采纳此结果并标记为 SUCCESS? (y/n): ").lower().strip()
                            if confirm == 'y':
                                db.save_record(file_path, "SUCCESS", new_url, new_title, new_tags)
                                print("✅ 数据库已更新为 SUCCESS")
                                processed = True 
                            else:
                                # 暂存结果供查看
                                gallery_url, title, tags = new_url, new_title, new_tags
                                print("   结果已暂存，您可以继续操作或打开网页确认。")
                        else:
                            print(f"❌ [扫描无结果] {result.get('message')}")
                    except Exception as e:
                        print(f"❌ 扫描过程出错: {e}")

                elif choice in ['n', 'no']:
                    processed = True
                    
                elif choice in ['o', 'open']:
                    if gallery_url and "http" in gallery_url:
                        webbrowser.open(gallery_url)
                    else:
                        print("❌ 无有效 URL")
                        
                elif choice in ['f', 'fail']:
                    db.save_record(file_path, "FAIL", gallery_url, title, tags)
                    print("🚫 已标记为 FAIL")
                    processed = True
                    
                elif choice in ['q', 'quit']:
                    return
                
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    manual_confirm_all()