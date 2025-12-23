# app/validator.py
import logging
from typing import Tuple, Optional, List
from .utils import calculate_similarity, parse_gallery_title

logger = logging.getLogger(__name__)

# 相似度阈值
SIMILARITY_THRESHOLD = 0.4

class ScanValidator:
    def __init__(self, searcher, translator):
        """
        初始化验证器
        :param searcher: 用于获取元数据的搜索器实例 (EHentaiHashSearcher)
        :param translator: 用于翻译标签的翻译器实例 (TagTranslator)
        """
        self.searcher = searcher
        self.translator = translator

    def check_title_match(self, clean_name: str, title_to_check: str) -> Tuple[bool, float]:
        """
        标题相似度检测
        :param clean_name: 本地文件及其清洗后的名称
        :param title_to_check: 待检查的画廊标题
        :return: (是否匹配, 相似度分数)
        """
        if not title_to_check:
            return False, 0.0
        
        # 1. 直接相似度 (文件名 vs 完整标题)
        sim_direct = calculate_similarity(clean_name, title_to_check)
        
        # 2. 解析后相似度 (文件名 vs 提取出的核心标题)
        # parse_gallery_title 会去除 (C99) [Group] 等干扰信息
        parsed = parse_gallery_title(title_to_check)
        parsed_title = parsed.get('title', '')
        sim_parsed = calculate_similarity(clean_name, parsed_title)
        
        # 取两者中较高的分数
        best_score = max(sim_direct, sim_parsed)
        return best_score >= SIMILARITY_THRESHOLD, best_score

    def check_tags_coverage(self, clean_name: str, tags_list: List[str]) -> bool:
        """
        标签覆盖度检测 (检查文件名中的作者或社团是否包含在画廊标签中)
        """
        if not tags_list:
            return False

        # 解析文件名中的元数据
        info = parse_gallery_title(clean_name)
        
        # 获取文件名中的作者和社团信息
        # 兼容处理: utils 可能返回 'group' 也可能返回 'circle'
        target_fields = {
            'artist': info.get('artist'), 
            'group': info.get('group') or info.get('circle')
        }
        
        # 将标签列表标准化 (转小写)
        normalized_tags = [str(t).lower() for t in tags_list if t]

        def check_field(field_value):
            if not field_value: 
                return False
            
            val = field_value.lower().strip()
            if len(val) < 2: 
                return False # 忽略太短的词(少于2字符)以防误判
            
            for tag in normalized_tags:
                # 移除 namespace (如 artist:xxx -> xxx)
                tag_val = tag.split(':', 1)[1] if ':' in tag else tag
                # 检查包含关系
                if val in tag_val.strip(): 
                    return True
            return False

        # 只要作者或社团任意一个匹配成功，即视为覆盖
        if check_field(target_fields['artist']) or check_field(target_fields['group']):
            return True
        return False

    def evaluate_scan_result(self, clean_name: str, scan_url: str) -> Tuple[bool, Optional[str], str]:
        """
        执行 4 步验证流程 (核心验证逻辑)
        
        返回: 
            (is_valid, final_title, final_tags_str)
            - is_valid: Boolean, 验证是否通过
            - final_title: String, 获取到的最佳标题 (即使验证失败也会返回，用于保护机制)
            - final_tags_str: String, 处理后的标签字符串
        """
        # 0. 获取详细元数据 (调用 searcher 的统一接口)
        meta = self.searcher.get_gallery_metadata(scan_url)
        
        if not meta:
            logger.warning(f"⚠️ 无法获取元数据: {scan_url}")
            return False, None, ""

        # 解包数据 (兼容 network.py 返回的字典结构)
        t_jp = meta.get('title_jpn', '')
        t_en = meta.get('title_en', '')
        raw_tags = meta.get('tags', [])
        
        # 准备翻译
        trans_tags = self.translator.translate_tags(raw_tags) if raw_tags else []
        combined_tags = (raw_tags or []) + trans_tags
        final_tags_str = ", ".join(combined_tags)
        
        # 确定最终标题 (优先使用日文原标，如果没有则使用英文)
        final_title = t_jp if t_jp else t_en 

        matched = False
        log_prefix = ""

        # === Step 1: 英文标题检测 ===
        is_match, score = self.check_title_match(clean_name, t_en)
        if is_match:
            matched = True
            log_prefix = f"✅ [英文标题匹配] Sim:{score:.2f}"
        
        # === Step 2: 原始 Tag 检测 (无需翻译) ===
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

        # === Step 4: 翻译 Tag 检测 (需翻译) ===
        if not matched:
            if self.check_tags_coverage(clean_name, combined_tags):
                matched = True
                log_prefix = "✅ [Trans Tag匹配]"

        if matched:
            logger.info(f"   {log_prefix}")
            return True, final_title, final_tags_str
        
        # 即使未匹配，也返回标题和标签，以便 Service 层进行'保护性'存储 (存为 MISMATCH)
        return False, final_title, final_tags_str