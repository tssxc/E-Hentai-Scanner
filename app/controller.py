# app/controller.py
"""
应用控制器层：定义具体的任务逻辑
"""
import logging
from pathlib import Path
from typing import Union, Optional
from . import config
from .services import ScanService
from .logger import setup_logging
from .common import verify_environment

# 配置默认日志
setup_logging(config.LOG_PATH_APP)
logger = logging.getLogger(__name__)


class AppController:
    """
    应用控制器：统一管理所有任务
    """
    def __init__(self):
        """初始化控制器和服务"""
        self.service = ScanService()

    def scan_new_files(self):
        """[任务] 扫描新文件"""
        logger.info("🚀 [任务] 扫描新文件")
        target_dir = config.DEFAULT_DIR
        
        # 环境检查
        if not verify_environment(self.service.searcher, str(target_dir)):
            logger.error("❌ 环境验证失败")
            return
        
        # 获取待处理文件
        files = self.service.get_pending_files(target_dir)
        if not files:
            logger.info("✅ 没有发现新文件")
            return

        # 执行批量扫描
        self.service.process_batch(files, scan_mode=config.DEFAULT_MODE)
        logger.info("🏁 [任务完成] 扫描新文件")

    def retry_failures(self):
        """
        [任务] 重试所有非成功项 (FAIL, NO_MATCH, MISMATCH等)
        强制使用 'second' (第二页) 模式，并开启详细调试日志
        """
        print("\n🚀 [任务] 启动全量重试 (模式: second) | 🐛 DEBUG模式已开启")
        
        # ================= 动态调整配置 =================
        # 1. 开启 DEBUG 级别日志
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
            
        # 2. 屏蔽第三方库噪音
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("charset_normalizer").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)
        
        # ================================================

        # 获取需要重试的文件 (现在会返回所有非 SUCCESS 的文件)
        retry_files = self.service.get_retry_files()
        
        if not retry_files:
            logger.info("✅ 没有非 SUCCESS 的记录，无需重扫。")
            return
        
        logger.info(f"📊 发现 {len(retry_files)} 个待重扫文件")
        
        # 转换为 Path 对象并过滤存在的文件
        files = [Path(f) for f in retry_files if Path(f).exists()]
        
        if not files:
            logger.warning("❌ 所有待重扫文件在本地都不存在")
            return
        
        # [核心修改] 强制使用 scan_mode='second'
        self.service.process_batch(files, scan_mode='second')
        
        logger.info("🏁 [任务完成] 全量重试结束")

    def scan_dedup(self):
        """[任务] 去重扫描（处理重复 URL）"""
        logger.info("🚀 [任务] 去重扫描")
        
        dup_files = self.service.get_duplicate_files()
        if not dup_files:
            logger.info("✅ 没有发现重复文件")
            return
        
        logger.info(f"📂 发现 {len(dup_files)} 个重复 URL 的文件")
        files = [Path(f) for f in dup_files if Path(f).exists()]
        
        if not files:
            logger.warning("⚠️ 所有重复文件都不存在")
            return
        
        self.service.process_batch(files, scan_mode=config.DEFAULT_MODE)
        logger.info("🏁 [任务完成] 去重扫描")

    def scan_single(self, file_path: Union[str, Path], scan_mode: Optional[str] = None):
        """[任务] 扫描单文件"""
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"❌ 文件不存在: {file_path}")
            return
        
        logger.info(f"🚀 [任务] 扫描单文件: {file_path.name}")
        result = self.service.scan_single(file_path, scan_mode=scan_mode)
        
        if result['success']:
            logger.info(f"✅ 扫描成功: {result.get('message')}")
        else:
            logger.warning(f"⚠️ 扫描失败: {result.get('message')}")
        
        return result

    def cleanup(self):
        """清理资源"""
        self.service.close()