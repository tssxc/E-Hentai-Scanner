# app/result_handler.py
import os
import logging
import traceback
from .exceptions import IpBlockedError, NetworkError, ParseError, EmptyArchiveError

logger = logging.getLogger(__name__)

class ResultHandler:
    def __init__(self, db_manager, validator):
        self.db = db_manager
        self.validator = validator

    def handle_search_result(self, path, new_url, searcher):
        if new_url == "NO_MATCH":
            return self._handle_no_match(path)
        elif new_url and "http" in new_url:
            return self._handle_match_success(path, new_url)
        else:
            return self._handle_unknown_format(path, new_url)

    def _handle_no_match(self, path):
        old_record = self.db.get_record_by_path(path)
        if old_record and old_record['status'] == "SUCCESS":
            logger.warning("🛡️ [保护] 原记录有效 (SUCCESS)，本次无匹配，跳过覆盖")
            return "FAIL"
        self._update_if_changed(path, "NO_MATCH", None, None, None)
        logger.debug("🈚 无匹配结果 (已更新状态)")
        return "FAIL"

    def _handle_match_success(self, path, new_url):
        try:
            file_name = os.path.basename(path)
            clean_name = os.path.splitext(file_name)[0]

            # === 调用 Validator 进行权威验证 ===
            is_valid, title, tags_str = self.validator.evaluate_scan_result(clean_name, new_url)
            
            final_status = "SUCCESS" if is_valid else "MISMATCH"
            
            if not is_valid:
                logger.warning(f"⚠️ [匹配存疑] 判定为不匹配 (存为 MISMATCH): {title}")
                
            # === 智能更新数据库 ===
            changed = self._update_if_changed(path, final_status, new_url, title, tags_str)
            
            if changed and final_status == "SUCCESS":
                logger.info(f"✨ [更新/新增] 数据已写入: {title}")
            elif not changed:
                logger.debug(f"💤 [跳过] 数据无变化")

            return final_status

        except Exception as e:
            logger.warning(f"⚠️ 验证过程异常: {e}", exc_info=True)
            self._update_if_changed(path, "ERROR", new_url, "Validation Error", str(e))
            return "ERROR"

    def _handle_unknown_format(self, path, new_url):
        logger.warning(f"⚠️ 未知返回格式: {new_url}")
        self._update_if_changed(path, "UNSUPPORTED", None, None, None)
        return "FAIL"

    def _update_if_changed(self, path, new_status, new_url, new_title, new_tags):
        old_record = self.db.get_record_by_path(path)
        if not old_record:
            self.db.save_record(path, new_status, new_url, new_title, new_tags)
            return True

        try:
            old_url = old_record['gallery_url']
            old_status = old_record['status']
        except Exception:
            self.db.save_record(path, new_status, new_url, new_title, new_tags)
            return True

        if old_url != new_url or old_status != new_status:
            if old_url != new_url:
                logger.info(f"🔄 [变更] URL 变动: {old_url} -> {new_url}")
            self.db.save_record(path, new_status, new_url, new_title, new_tags)
            return True
        return False

    def handle_exception(self, path, error):
        if isinstance(error, IpBlockedError):
            logger.critical(f"🛑 {error}") 
            return "STOP"
        elif isinstance(error, NetworkError):
            logger.warning(f"⚠️ {error}")
            self.db.save_record(path, status="NETWORK_FAIL")
            return "CONTINUE"
        elif isinstance(error, (ParseError, EmptyArchiveError)):
            logger.error(f"❌ {error}")
            self.db.save_record(path, status="FILE_ERROR")
            return "CONTINUE"
        else:
            logger.error(f"☠️ 系统异常: {error}")
            self.db.save_record(path, status="ERROR")
            return "CONTINUE"