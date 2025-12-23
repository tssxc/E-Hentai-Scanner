# tools/similarity_rescan.py
import os
import sys
import logging
import re
import html
import time
import traceback

# 1. 路径设置：确保能找到项目根目录和 app 模块
# 获取当前脚本所在目录 (tools/)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (E-Hentai-Scanner/)
project_root = os.path.dirname(current_dir)

# 将项目根目录加入 Python 搜索路径，以便导入 app.xxx
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 2. 导入项目模块 (此时已在 path 中)
try:
    from app import config
    from app.common import initialize_components
    from app.utils import calculate_similarity, perform_random_sleep, parse_gallery_title
    from app.scanner_core import scan_single_file
    from app.logger import setup_logging
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("   请确保在项目根目录下运行，或检查目录结构。")
    sys.exit(1)

# 设置单独的日志文件
LOG_FILE = os.path.join(project_root, "logs", "similarity_rescan.log")
logger = setup_logging(LOG_FILE)

# 相似度阈值
SIMILARITY_THRESHOLD = 0.4

class SimilarityRescanner:
    def __init__(self):
        """
        初始化扫描器组件 (正式运行模式)
        """
        self.db = None
        self.searcher = None
        self.translator = None
        self.handler = None
        
        try:
            # 解包组件 (注意：根据 app/common.py 的实际返回调整解包数量)
            # 假设 initialize_components 返回: db, searcher, translator, task_manager, result_handler, _, _
            comps = initialize_components()
            self.db = comps[0]
            self.searcher = comps[1]
            self.translator = comps[2]
            self.handler = comps[4]
            
            logger.info("✅ 组件初始化完成 (Tools模式)")
        except Exception as e:
            logger.error(f"❌ 组件初始化失败: {e}")
            logger.debug(traceback.format_exc())
            sys.exit(1)

    def close(self):
        if self.db:
            self.db.close()

    def get_detailed_metadata(self, gallery_url):
        """
        获取画廊的详细元数据
        """
        if not gallery_url or not self.searcher:
            return None, None, []

        match = re.search(r'/g/(\d+)/([\w]+)', gallery_url)
        if not match:
            return None, None, []
        
        gid, token = int(match.group(1)), match.group(2)
        payload = {"method": "gdata", "gidlist": [[gid, token]], "namespace": 1}

        try:
            res = self.searcher.session.post(self.searcher.api_url, json=payload, timeout=10)
            data = res.json()
            
            if 'gmetadata' in data and data['gmetadata']:
                gmeta = data['gmetadata'][0]
                t_jpn = html.unescape(gmeta.get('title_jpn') or "")
                t_en = html.unescape(gmeta.get('title') or "")
                tags = gmeta.get('tags', []) 
                
                # 确保两个标题字段都有值
                if not t_jpn and t_en: t_jpn = t_en
                if not t_en and t_jpn: t_en = t_jpn
                
                return t_jpn, t_en, tags
        except Exception as e:
            logger.warning(f"⚠️ [Meta-Fetch] 获取元数据失败: {e}")
        
        return None, None, []

    def check_title_match(self, clean_name, title_to_check):
        """
        单一标题相似度检测
        """
        if not title_to_check:
            return False, 0.0

        # 1. 直接相似度
        sim_direct = calculate_similarity(clean_name, title_to_check)
        
        # 2. 解析后相似度 (提取核心标题)
        parsed_title = parse_gallery_title(title_to_check)['title']
        sim_parsed = calculate_similarity(clean_name, parsed_title)
        
        best_score = max(sim_direct, sim_parsed)
        return best_score >= SIMILARITY_THRESHOLD, best_score

    def check_tags_coverage(self, clean_name, tags_list):
        """
        检查 Tag 覆盖情况
        """
        if not tags_list:
            return False

        info = parse_gallery_title(clean_name)
        target_fields = {
            'artist': info.get('artist'), 
            'group': info.get('group') # 这里对应 utils.py 修改后的 group
        }
        
        normalized_tags = [str(t).lower() for t in tags_list if t]

        def check_field_in_tags(field_value):
            if not field_value: return False
            val = field_value.lower().strip()
            if len(val) < 2: return False
            for tag in normalized_tags:
                # 移除 namespace (如 artist:xxx -> xxx)
                tag_val = tag.split(':', 1)[1] if ':' in tag else tag
                if val in tag_val.strip(): return True
            return False

        match_log = []
        if check_field_in_tags(target_fields['artist']): match_log.append(f"Artist[{target_fields['artist']}]")
        if check_field_in_tags(target_fields['group']): match_log.append(f"Group[{target_fields['group']}]")

        if match_log:
            logger.info(f"   🏷️ [Tag验证成功] {', '.join(match_log)}")
            return True
        return False

    def evaluate_scan_result(self, clean_name, scan_url):
        """
        执行 4 步验证流程
        返回: (是否成功, 标题, 标签字符串)
        """
        # 0. 获取元数据
        t_jp, t_en, raw_tags = self.get_detailed_metadata(scan_url)
        
        # 准备翻译
        trans_tags = self.translator.translate_tags(raw_tags) if raw_tags else []
        combined_tags = (raw_tags or []) + trans_tags
        final_tags_str = ", ".join(combined_tags)
        final_title = t_jp or t_en # 优先存日文标题

        matched = False
        log_prefix = ""

        # === Step 1: 英文标题检测 ===
        is_match, score = self.check_title_match(clean_name, t_en)
        if is_match:
            matched = True
            log_prefix = f"✅ [英文标题匹配] Sim:{score:.2f}"
        
        # === Step 2: 原始 Tag 检测 ===
        if not matched:
            if self.check_tags_coverage(clean_name, raw_tags):
                matched = True
                log_prefix = "✅ [Raw Tag匹配]"

        # === Step 3: 日文/原标题检测 ===
        if not matched:
            is_match, score = self.check_title_match(clean_name, t_jp)
            if is_match:
                matched = True
                log_prefix = f"✅ [日文标题匹配] Sim:{score:.2f}"

        # === Step 4: 翻译 Tag 检测 ===
        if not matched:
            if self.check_tags_coverage(clean_name, combined_tags):
                matched = True
                log_prefix = "✅ [Trans Tag匹配]"

        if matched:
            logger.info(f"   {log_prefix}")
            return True, final_title, final_tags_str
        
        return False, final_title, final_tags_str

    def process_single_file(self, file_path):
        """
        核心处理流程
        """
        if not os.path.exists(file_path):
            return

        record = self.db.get_record_by_path(file_path)
        if not record:
            return

        file_name = os.path.basename(file_path)
        clean_name = os.path.splitext(file_name)[0]
        
        current_data = {
            'url': record['gallery_url'],
            'title': record['title'],
            'tags': record['tags']
        }

        logger.info(f"🔍 [处理] {file_name}")

        # === 阶段 1: 检查本地数据库 ===
        db_tags_list = [t.strip() for t in (current_data['tags'] or "").split(',')] if current_data['tags'] else []
        
        m_title, s_title = self.check_title_match(clean_name, current_data['title'])
        m_tag = self.check_tags_coverage(clean_name, db_tags_list)
        
        if m_title or m_tag:
            logger.info(f"   ✅ [本地记录有效] TitleSim:{s_title:.2f} / TagMatch:{m_tag}")
            return

        logger.warning(f"   ⚠️ [本地校验失败] 开始重扫流程...")

        # === 阶段 2: 封面扫描 ===
        resolved = False
        perform_random_sleep()
        logger.info("   🔄 尝试: 封面扫描...")
        
        res_cover = scan_single_file(file_path, self.searcher, self.handler, scan_mode='cover')
        if res_cover['success']:
            scan_url = res_cover['url']
            is_success, new_title, new_tags = self.evaluate_scan_result(clean_name, scan_url)
            
            current_data.update({'url': scan_url, 'title': new_title, 'tags': new_tags})

            if is_success:
                resolved = True
                logger.info("   🎉 封面扫描成功并匹配!")
                self.db.save_record(file_path, 'SUCCESS', scan_url, new_title, new_tags)

        # === 阶段 3: 第10页扫描 ===
        if not resolved:
            perform_random_sleep()
            logger.info("   🔄 尝试: 第10页扫描...")
            
            res_sec = scan_single_file(file_path, self.searcher, self.handler, scan_mode='second')
            if res_sec['success']:
                scan_url = res_sec['url']
                is_success, new_title, new_tags = self.evaluate_scan_result(clean_name, scan_url)
                
                current_data.update({'url': scan_url, 'title': new_title, 'tags': new_tags})

                if is_success:
                    resolved = True
                    logger.info("   🎉 第10页扫描成功并匹配!")
                    self.db.save_record(file_path, 'SUCCESS', scan_url, new_title, new_tags)

        # === 阶段 4: 最终判定 ===
        if not resolved:
            logger.warning(f"   📉 [失败] 所有手段均未匹配，更新为 MISMATCH")
            self.db.save_record(
                file_path, 
                status='MISMATCH', 
                url=current_data['url'], 
                title=current_data['title'], 
                tags=current_data['tags']
            )

    def run_batch_scan(self):
        """批量运行"""
        all_paths = self.db.get_all_processed_paths()
        logger.info(f"📂 数据库记录总数: {len(all_paths)}")
        
        count = 0
        for idx, file_path in enumerate(all_paths, 1):
            if not os.path.exists(file_path): continue
            
            # 仅处理 SUCCESS 状态的记录
            record = self.db.get_record_by_path(file_path)
            if not record or record['status'] != 'MISMATCH': continue
            
            self.process_single_file(file_path)
            count += 1
            
            if count % 10 == 0:
                logger.info(f"⏳ 已处理 {count} 个文件...")
        
        logger.info(f"🏁 扫描任务结束，共处理: {count} 个")


if __name__ == "__main__":
    app = SimilarityRescanner()
    try:
        app.run_batch_scan()
    except KeyboardInterrupt:
        print("\n🛑 用户中断")
    finally:
        app.close()