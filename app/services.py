# app/services.py
import logging
from pathlib import Path
from typing import Dict, Any

from .database import DatabaseManager
from .network import EHentaiHashSearcher
from .validator import ScannerValidator

logger = logging.getLogger(__name__)

class ScannerService:
    def __init__(self, db: DatabaseManager, searcher: EHentaiHashSearcher, translator):
        self.db = db
        self.searcher = searcher
        self.validator = ScannerValidator(searcher, translator)

    def process_file(self, file_path: Path, mode='cover') -> Dict[str, Any]:
        """
        处理单个文件的主流程
        """
        file_name = file_path.name

        # 1. 基础检查
        if not file_path.exists():
            return self._handle_failure(file_path, 'FAILED', 'File not found')
            
        clean_name = file_path.stem

        # 2. 执行搜索 (Hash 或 Title)
        try:
            search_res = self.searcher.process_archive(file_path, target=mode)
        except Exception as e:
            logger.error(f"❌ 搜索异常: {e}")
            search_res = f"ERROR: {str(e)}"

        # 3. 处理搜索结果无效的情况
        if not search_res or not search_res.startswith('http'):
            note = self._map_error_to_note(search_res)
            return self._handle_failure(file_path, 'FAILED', note, search_res)

        # 4. 验证结果 (Validator)
        is_valid, final_title, final_tags = self.validator.evaluate_scan_result(clean_name, search_res, mode=mode)

        if is_valid:
            # === 成功 ===
            self.db.save_record(
                file_path=file_path,
                status='SUCCESS',
                url=search_res,
                title=final_title,
                tags=final_tags
            )
            logger.info(f"✅ [匹配成功] {file_name}\n   => 📘 {final_title}")
            return {'status': 'SUCCESS', 'file_name': file_name, 'title': final_title}
        
        else:
            # === 验证失败 (Mismatch) ===
            status_code = 'MISMATCH' if final_title else 'FAILED'
            note = "标题/标签匹配度不足" if final_title else "获取元数据失败"
            
            self.db.save_record(
                file_path=file_path,
                status=status_code,
                url=search_res,
                title=final_title or "Unknown",
                tags=final_tags,
                note=note
            )
            logger.warning(f"⚠️ [验证不符] {file_name} | 原因: {note}")
            return {'status': status_code, 'file_name': file_name, 'note': note}

    def _handle_failure(self, file_path: Path, status: str, note: str, url: str = None) -> Dict:
        """统一处理失败落库"""
        self.db.save_record(file_path, status=status, note=note, url=url)
        logger.info(f"🌑 [处理失败] {file_path.name} | 原因: {note}")
        return {'status': status, 'file_name': file_path.name, 'note': note}

    def _map_error_to_note(self, search_res: str) -> str:
        """将搜索错误码映射为人类可读的备注"""
        if search_res == "NO_MATCH":
            return "未找到匹配项 (Hash/Title)"
        if search_res == "NO_IMAGES":
            return "压缩包内无有效图片"
        if search_res == "FILE_ERROR":
            return "文件读取或解压失败"
        if search_res and search_res.startswith("ERROR"):
            return f"搜索错误: {search_res}"
        return "搜索无结果或未知错误"