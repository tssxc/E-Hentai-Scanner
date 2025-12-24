# tools/batch_rescan_second.py
"""
工具脚本：批量对所有非 SUCCESS 状态的记录进行【第二页/第10页】扫描
(已开启 DEBUG 模式，显示详细匹配过程)
"""
import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.services import ScanService
from app import config

# ================= 配置日志 =================
# 1. 设置全局日志级别为 DEBUG，以显示详细信息
logging.basicConfig(level=logging.DEBUG, format='%(message)s')

# 2. 屏蔽第三方库的噪音 (否则控制台会被 HTTP 请求日志淹没)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("charset_normalizer").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def main():
    print("🚀 [工具] 启动全量批量重扫 (模式: second) | 🐛 DEBUG模式已开启")
    print("ℹ️  目标: 数据库中所有状态不是 'SUCCESS' 的记录")
    print("ℹ️  扫描逻辑: 提取压缩包的 第10张图片 (若不足10张则取最后一张) 进行哈希搜索")
    print("-" * 50)
    
    # 初始化服务
    try:
        service = ScanService()
    except Exception as e:
        print(f"❌ 服务初始化失败: {e}")
        return
    
    try:
        # 1. 查询数据库：获取所有非 SUCCESS 的记录
        table = service.db.table_name
        sql = f"SELECT file_path, status FROM {table} WHERE status != 'SUCCESS'"
        
        service.db.cursor.execute(sql)
        rows = service.db.cursor.fetchall()
        
        if not rows:
            print("✅ 数据库中没有发现非 SUCCESS 的记录，无需重扫。")
            return
            
        print(f"📊 发现 {len(rows)} 条待处理记录。")
        
        # 2. 筛选存在的本地文件
        files_to_scan = []
        for row in rows:
            p = Path(row['file_path'])
            if p.exists():
                files_to_scan.append(p)
        
        if not files_to_scan:
            print("❌ 所有待处理记录对应的本地文件都不存在。")
            return
            
        print(f"📂 有效本地文件数: {len(files_to_scan)}")
        print("=" * 50)
        
        # 3. 执行批量扫描
        # service.process_batch 内部会记录 INFO 日志
        # app.utils.calculate_similarity 等模块会记录 DEBUG 日志
        service.process_batch(files_to_scan, scan_mode='second')
        
        print("\n" + "=" * 50)
        print("🎉 批量重扫完成！")
        print("💡 您现在可以看到 [Sim] 相似度分数和 [parse] 标题解析过程了。")

    except KeyboardInterrupt:
        print("\n🛑 用户强制中断任务")
    except Exception as e:
        print(f"\n❌ 发生未预期的错误: {e}")
    finally:
        if 'service' in locals():
            service.close()

if __name__ == "__main__":
    main()