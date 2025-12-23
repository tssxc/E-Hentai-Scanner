# modules/result_handler.py
import os
import logging
import traceback
from .exceptions import IpBlockedError, NetworkError, ParseError, EmptyArchiveError
from .utils import calculate_similarity

logger = logging.getLogger(__name__)


class ResultHandler:
    def __init__(self, db_manager, translator):
        self.db = db_manager
        self.translator = translator

    def handle_search_result(self, path, new_url, searcher):
        """
        处理搜索结果，并智能对比更新数据库
        """
        # 1. 没有任何结果 (NO_MATCH)
        if new_url == "NO_MATCH":
            # === [新增逻辑] 检查旧数据，防止覆盖 SUCCESS ===
            old_record = self.db.get_record_by_path(path)
            if old_record:
                try:
                    # 获取旧状态 (兼容 sqlite3.Row 和 字典访问)
                    old_status = old_record['status']
                    
                    # 如果旧状态已经是成功，但这次没搜到，则【不修改】数据库
                    if old_status == "SUCCESS":
                        logger.warning("🛡️ [保护] 原记录有效 (SUCCESS)，本次无匹配，跳过覆盖")
                        # 返回 FAIL 表示本次搜索没拿到新东西，但不影响数据库
                        return "FAIL"
                except Exception:
                    # 如果读取状态出错，忽略保护逻辑，继续向下执行
                    pass

            # 如果没有旧记录，或者旧记录不是 SUCCESS，才更新为 NO_MATCH
            self._update_if_changed(path, "NO_MATCH", None, None, None)
            # 无匹配属于常规情况，降低为 DEBUG，避免刷屏
            logger.debug("🈚 无匹配结果 (已更新状态)")
            return "FAIL"
            
        # 2. 成功获取 URL
        elif new_url and "http" in new_url:
            try:
                # 获取新元数据
                metadata = searcher.get_gallery_metadata(new_url)
                title = metadata.get('title', 'Unknown')
                tags = metadata.get('tags', [])
                tag_str = ", ".join(self.translator.translate_tags(tags))

                # ================= 🔍 相似度检查 =================
                file_name = os.path.basename(path)
                clean_name = os.path.splitext(file_name)[0]  # 去掉后缀

                sim_score = calculate_similarity(clean_name, title)
                log_msg = (
                    f"🔍 相似度: {sim_score:.2f} | "
                    f"File: {clean_name[:20]}... <-> Title: {title[:20]}..."
                )

                # 阈值：低于 0.4 视为高风险，提示人工核查
                if sim_score < 0.4:
                    logger.warning(f"⚠️ {log_msg} (差异过大，请人工核查!)")
                else:
                    # 正常相似度仅在 DEBUG 输出，减少日志噪音
                    logger.debug(log_msg)
                # =================================================
                
                # === 智能更新检查 (核心逻辑) ===
                changed = self._update_if_changed(path, "SUCCESS", new_url, title, tag_str)
                
                if changed:
                    logger.info(f"✨ [更新/新增] 数据已写入: {title}")
                else:
                    # 无变化属于正常情况，降低为 DEBUG
                    logger.debug(f"💤 [跳过] 数据无变化: {title}")

                return "SUCCESS"

            except Exception as e:
                logger.warning(f"⚠️ URL有效但元数据获取失败: {e}")
                # 即使元数据失败，如果 URL 变了也要存
                self._update_if_changed(path, "SUCCESS", new_url, "Meta Error", "")
                return "SUCCESS"
        
        # 3. 其他未知格式
        else:
            logger.warning(f"⚠️ 未知返回格式: {new_url}")
            self._update_if_changed(path, "UNSUPPORTED", None, None, None)
            return "FAIL"

    def _update_if_changed(self, path, new_status, new_url, new_title, new_tags):
        """
        智能更新数据库记录
        只有当状态或 URL 发生变化时才更新
        
        Args:
            path: 文件路径
            new_status: 新状态
            new_url: 新 URL
            new_title: 新标题
            new_tags: 新标签
        
        Returns:
            bool: 是否进行了更新
        """
        old_record = self.db.get_record_by_path(path)
        
        
        # 如果没有旧记录，直接保存新记录
        if not old_record:
            self.db.save_record(path, new_status, new_url, new_title, new_tags)
            return True

        # 获取旧记录的值
        try:
            old_url = old_record['gallery_url']
            old_status = old_record['status']
        except (KeyError, TypeError) as e:
            # 如果无法读取旧记录，视为需要更新
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
        
        Args:
            path: 文件路径
            error: 异常对象
        
        Returns:
            str: 操作指令
                - "STOP": 停止扫描（如 IP 被封）
                - "CONTINUE": 继续扫描
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