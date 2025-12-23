# modules/scanner_core.py
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, TypedDict
from . import config
from .utils import perform_random_sleep

logger = logging.getLogger(__name__)

class ScanResult(TypedDict):
    success: bool
    status: str
    url: Optional[str]
    message: str
    title: Optional[str]
    action: Optional[str]

def scan_single_file(file_path: str, searcher, handler, scan_mode: Optional[str] = None) -> ScanResult:
    """扫描单个文件并返回结构化结果"""
    scan_mode = scan_mode or config.DEFAULT_MODE
    path_obj = Path(file_path)
    
    if not path_obj.exists():
        return {
            'success': False, 'status': 'ERROR', 'url': None, 
            'message': f'文件不存在: {file_path}', 'title': None, 'action': None
        }
    
    logger.debug(f"🔍 [单文件扫描] {path_obj.name} (模式: {scan_mode})")
    
    try:
        # 执行搜索
        url = searcher.process_archive(path_obj, target=scan_mode)
        
        # 处理结果
        status = handler.handle_search_result(str(path_obj), url, searcher)
        
        if status == "STOP":
            return {
                'success': False, 'status': 'STOP', 'url': None,
                'message': '触发停止信号 (IP 被封)', 'title': None, 'action': 'STOP'
            }
        elif status == "SUCCESS":
            # 获取记录详情
            record = handler.db.get_record_by_path(str(path_obj))
            title = record['title'] if record else 'Unknown'
            return {
                'success': True, 'status': 'SUCCESS', 'url': url,
                'message': f'成功找到: {title}', 'title': title, 'action': None
            }
        else:
            return {
                'success': False, 'status': 'FAIL', 'url': url,
                'message': '未找到匹配结果' if url == "NO_MATCH" else f'状态: {status}',
                'title': None, 'action': None
            }
            
    except KeyboardInterrupt:
        logger.warning("🛑 用户强制中断")
        return {
            'success': False, 'status': 'INTERRUPTED', 'url': None,
            'message': '用户中断', 'title': None, 'action': 'STOP'
        }
    except Exception as e:
        action = handler.handle_exception(str(path_obj), e)
        return {
            'success': False, 'status': 'ERROR', 'url': None,
            'message': f'错误: {str(e)}', 'title': None, 'action': action
        }

def run_batch_scan(tasks: List[str], description: str, searcher, handler, scan_mode: str):
    """批量扫描通用入口"""
    if not tasks:
        logger.info(f"✅ [{description}] 无任务，跳过。")
        return

    # 应用 Debug 模式限制
    if config.SCAN_LIMIT > 0 and len(tasks) > config.SCAN_LIMIT:
        logger.warning(f"✂️ [{description}] Debug限制生效: 仅处理前 {config.SCAN_LIMIT} 个")
        tasks = tasks[:config.SCAN_LIMIT]

    total = len(tasks)
    logger.info(f"{'='*20} 开始: {description} (总数: {total}) {'='*20}")
    
    success_count = 0

    for idx, path_str in enumerate(tasks, 1):
        path = Path(path_str)
        if not path.exists():
            logger.warning(f"⚠️ 文件已丢失，跳过: {path.name}")
            continue

        logger.debug(f"[{description}] [{idx}/{total}] {path.name}")
        
        try:
            url = searcher.process_archive(path, target=scan_mode)
            status = handler.handle_search_result(str(path), url, searcher)
            
            if status == "STOP": 
                logger.critical("🛑 触发停止信号")
                return
            elif status == "SUCCESS": 
                success_count += 1
                
        except KeyboardInterrupt:
            logger.warning("🛑 用户强制中断")
            return
        except Exception as e:
            action = handler.handle_exception(str(path), e)
            if action == "STOP": return

        perform_random_sleep()

    logger.info(f"🏁 [{description}] 任务完成。成功: {success_count}/{len(tasks)}")
