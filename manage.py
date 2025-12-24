# manage.py
"""
E-Hentai Scanner 统一管理入口
用于通过命令行调用应用功能
"""
import sys
import argparse
from app.controller import AppController

def main():
    parser = argparse.ArgumentParser(
        description="E-Hentai Scanner CLI Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 使用子命令模式，以便为不同命令提供不同参数
    subparsers = parser.add_subparsers(dest='command', help='可用命令', required=True)

    # 1. 命令: scan_new (扫描新文件)
    scan_parser = subparsers.add_parser('scan_new', help='[增量] 扫描新文件 (默认模式)')

    # 2. 命令: retry (重试)
    # 逻辑已在 Controller 中修改为：全量扫描非成功项 + 强制第二页模式 + 开启Debug
    retry_parser = subparsers.add_parser('retry', help='[重扫] 重试所有非成功项 (强制使用第二页模式 + Debug日志)')

    # 3. 命令: dedup (去重)
    dedup_parser = subparsers.add_parser('dedup', help='[维护] 扫描重复URL的文件')
    
    # 4. 命令: single (单文件)
    single_parser = subparsers.add_parser('single', help='[测试] 扫描单个文件')
    single_parser.add_argument('path', help='文件路径')
    single_parser.add_argument(
        '--mode', 
        choices=['cover', 'second'], 
        default='cover', 
        help='扫描模式: cover=封面(默认), second=第10页/末页'
    )

    # 解析参数
    args = parser.parse_args()
    
    # 初始化控制器
    app = AppController()
    
    try:
        if args.command == 'scan_new':
            app.scan_new_files()
            
        elif args.command == 'retry':
            # 调用修改后的 retry_failures，它会自动开启 Debug 和 Second Mode
            app.retry_failures()
            
        elif args.command == 'dedup':
            app.scan_dedup()
            
        elif args.command == 'single':
            # 支持通过命令行指定模式
            app.scan_single(args.path, scan_mode=args.mode)
            
    except KeyboardInterrupt:
        print("\n🛑 用户停止")
    except Exception as e:
        print(f"❌ 发生严重错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        app.cleanup()

if __name__ == "__main__":
    main()