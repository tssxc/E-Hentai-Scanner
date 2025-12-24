# app/result_handler.py
import os
import logging
import traceback
from .exceptions import IpBlockedError, NetworkError, ParseError, EmptyArchiveError

logger = logging.getLogger(__name__)

class ResultHandler:
    def __init__(self, db_manager, validator):
        """
        初始化结果处理器
        :param db_manager: 数据库管理器
        :param validator: 扫描验证器 (ScanValidator)
        """
        self.db = db_manager
        self.validator = validator

    def handle_search_result(self, path, new_url, searcher):
        """
        处理搜索结果，并智能对比更新数据库
        (主入口函数，负责分发逻辑)
        """
        # 1. 没有任何结果 (NO_MATCH)
        if new_url == "NO_MATCH":
            return self._handle_no_match(path)
            
        # 2. 成功获取 URL
        elif new_url and "http" in new_url:
            return self._handle_match_success(path, new_url)
        
        # 3. 其他未知格式
        else:
            return self._handle_unknown_format(path, new_url)

    def _handle_no_match(self, path):
        """
        处理无匹配结果的情况
        包含：检查旧数据，防止覆盖 SUCCESS 的保护逻辑
        """
        old_record = self.db.get_record_by_path(path)
        if old_record:
            try:
                # 获取旧状态
                old_status = old_record['status']
                
                # 🛡️ [保护] 如果旧状态已经是成功，但这次没搜到，则【不修改】数据库
                if old_status == "SUCCESS":
                    logger.warning("🛡️ [保护] 原记录有效 (SUCCESS)，本次无匹配，跳过覆盖")
                    return "FAIL"
            except Exception:
                pass

        # 如果没有旧记录，或者旧记录不是 SUCCESS，才更新为 NO_MATCH
        self._update_if_changed(path, "NO_MATCH", None, None, None)
        logger.debug("🈚 无匹配结果 (已更新状态)")
        return "FAIL"

    def _handle_match_success(self, path, new_url):
        """
        处理匹配成功的情况
        [核心修改] 将验证逻辑全权委托给 Validator
        """
        try:
            file_name = os.path.basename(path)
            clean_name = os.path.splitext(file_name)[0]

            # === 调用 Validator 进行验证 ===
            # Validator 内部会去获取元数据、翻译标签、计算相似度、检查 Tag 覆盖
            is_valid, title, tags_str = self.validator.evaluate_scan_result(clean_name, new_url)
            
            # 根据 Validator 的结果决定状态
            if is_valid:
                final_status = "SUCCESS"
                log_msg = f"✨ [匹配确认] {title}"
            else:
                # 验证失败（相似度低且 Tag 对不上），存为 MISMATCH
                final_status = "MISMATCH" 
                log_msg = f"⚠️ [匹配存疑] 判定为不匹配: {title}"
                # 提示需要在日志中注意
                if logger.isEnabledFor(logging.INFO):
                    logger.info(log_msg)
                    logger.info(f"   -> 建议人工核查: {path}")

            # === 智能更新数据库 ===
            # 即使是 MISMATCH，我们也把 URL 和标题存进去，方便后续人工修正
            changed = self._update_if_changed(path, final_status, new_url, title, tags_str)
            
            if changed and final_status == "SUCCESS":
                # 只有 SUCCESS 且发生变化时才打印高亮日志，MISMATCH 上面已经打过了
                logger.info(f"✨ [更新/新增] 数据已写入: {title}")
            elif not changed:
                logger.debug(f"💤 [跳过] 数据无变化: {title}")

            return final_status

        except Exception as e:
            logger.warning(f"⚠️ 验证过程异常: {e}", exc_info=True)
            # 如果验证过程崩了，记录为 ERROR
            self._update_if_changed(path, "ERROR", new_url, "Validation Error", str(e))
            return "ERROR"

    def _handle_unknown_format(self, path, new_url):
        """处理未知的返回 URL 格式"""
        logger.warning(f"⚠️ 未知返回格式: {new_url}")
        self._update_if_changed(path, "UNSUPPORTED", None, None, None)
        return "FAIL"

    def _update_if_changed(self, path, new_status, new_url, new_title, new_tags):
        """
        智能更新数据库记录
        只有当状态或 URL 发生变化时才更新
        """
        old_record = self.db.get_record_by_path(path)
        
        # 如果没有旧记录，直接保存
        if not old_record:
            self.db.save_record(path, new_status, new_url, new_title, new_tags)
            return True

        # 获取旧记录的值
        try:
            old_url = old_record['gallery_url']
            old_status = old_record['status']
        except (KeyError, TypeError) as e:
            logger.warning(f"⚠️ 无法读取旧记录字段: {e}，将执行更新")
            self.db.save_record(path, new_status, new_url, new_title, new_tags)
            return True

        # 只有当状态或 URL 发生变化时才更新
        if old_url != new_url or old_status != new_status:
            if old_url != new_url:
                logger.info(f"🔄 [变更] URL 发生变化!")
                logger.info(f"   🔴 旧: {old_url}")
                logger.info(f"   🟢 新: {new_url}")
            self.db.save_record(path, new_status, new_url, new_title, new_tags)
            return True
        
        return False

    def handle_exception(self, path, error):
        """
        处理扫描过程中出现的异常
        """
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
            logger.debug(traceback.format_exc())
            self.db.save_record(path, status="ERROR")
            return "CONTINUE"