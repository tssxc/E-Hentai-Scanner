# app/validator.py
import logging
from typing import Tuple, Optional, List

# 确保 app/utils.py 里有 calculate_hybrid_similarity
from .utils import calculate_hybrid_similarity, parse_gallery_title

logger = logging.getLogger(__name__)

# 相似度阈值 (混合算法下建议 0.6)
SIMILARITY_THRESHOLD = 0.6

class ScannerValidator:
    def __init__(self, searcher, translator):
        """
        初始化验证器
        :param searcher: 网络搜索器实例
        :param translator: 翻译器实例
        """
        self.searcher = searcher
        self.translator = translator

    def check_title_match(self, clean_name: str, title_to_check: str, is_strict: bool = False) -> Tuple[bool, float]: 
        """
        标题匹配检测 (支持严格模式)
        """
        if not clean_name or not title_to_check:
            return False, 0.0
        
        name_lower = clean_name.lower().strip()
        title_lower = title_to_check.lower().strip()

        # --- [Strict 模式] ---
        if is_strict:
            # 1. 尝试直接全等
            if name_lower == title_lower:
                return True, 1.0
            
            # 2. 尝试解析后全等 (核心标题必须完全一致)
            parsed = parse_gallery_title(title_to_check)
            core_title = parsed.get('title', '').lower().strip()
            
            if core_title and name_lower == core_title:
                return True, 1.0
                
            return False, 0.0

        # --- [模糊匹配模式] ---
        
        # 1. 直接相似度 (混合算法)
        sim_direct = calculate_hybrid_similarity(clean_name, title_to_check)
        
        # 2. 解析后相似度 (核心标题)
        parsed = parse_gallery_title(title_to_check)
        parsed_title = parsed.get('title', '')
        
        sim_parsed = 0.0
        if parsed_title and len(parsed_title) >= 2:
            sim_parsed = calculate_hybrid_similarity(clean_name, parsed_title)
        
        best_score = max(sim_direct, sim_parsed)
        
        # Debug日志
        if best_score > 0.4:
            logger.debug(f"   🔍 对比(Strict={is_strict}): '{clean_name}' vs '{title_to_check[:15]}...' -> {best_score:.2f}")

        return best_score >= SIMILARITY_THRESHOLD, best_score

    def check_tags_coverage(self, clean_name: str, tags_list: List[str]) -> bool:
        """
        [这就是之前缺失的方法]
        标签覆盖度检测: 检查文件名中的作者/社团是否包含在 Tag 列表中
        """
        if not tags_list:
            return False

        # 从文件名解析元数据
        info = parse_gallery_title(clean_name)
        
        # 获取待检测目标 (Artist / Group)
        targets = set()
        if info.get('artist'): targets.add(info['artist'].lower())
        if info.get('group'): targets.add(info['group'].lower())
        
        # 如果文件名里没提取出作者或社团，就无法进行 Tag 覆盖校验
        if not targets:
            return False

        # 预处理标签列表 (全部转小写，移除 'artist:' 等前缀)
        normalized_tags = set()
        for tag in tags_list:
            if not tag: continue
            tag_clean = tag.lower().strip()
            if ':' in tag_clean:
                tag_clean = tag_clean.split(':', 1)[1].strip()
            normalized_tags.add(tag_clean)

        # 检查包含关系
        for target in targets:
            if len(target) < 2: continue 
            
            for tag in normalized_tags:
                # 只要目标词出现在 Tag 中 (包含关系) 即算命中
                if target in tag:
                    logger.debug(f"   🎯 Tag覆盖命中: '{target}' in '{tag}'")
                    return True
                    
        return False

    def evaluate_scan_result(self, clean_name: str, scan_url: str, mode: str = 'cover') -> Tuple[bool, Optional[str], str]:
        """
        执行验证流程
        :param mode: 当前扫描模式，如果是 'title' 则开启严格匹配
        """
        # 0. 获取元数据
        meta = self.searcher.get_gallery_metadata(scan_url)
        if not meta:
            logger.warning(f"⚠️ 无法获取元数据: {scan_url}")
            return False, None, ""

        # 解包数据
        t_jp = meta.get('title_jpn', '') or ""
        t_en = meta.get('title_en', '') or ""
        raw_tags = meta.get('tags', [])
        
        # 翻译标签
        trans_tags = self.translator.translate_tags(raw_tags) if raw_tags else []
        combined_tags = (raw_tags or []) + trans_tags
        final_tags_str = ", ".join(combined_tags)
        
        final_title = t_jp if t_jp else t_en 

        # 判定是否开启严格模式
        is_strict_mode = (mode == 'title')

        # === 验证流程 ===
        
        # 1. 英文标题检测
        matched, score = self.check_title_match(clean_name, t_en, is_strict=is_strict_mode)
        if matched:
            logger.debug(f"✅ [匹配成功] 英文标题")
            return True, final_title, final_tags_str
        
        # 2. 原始 Tag 检测
        if self.check_tags_coverage(clean_name, raw_tags):
            logger.debug(f"✅ [匹配成功] 原始标签覆盖")
            return True, final_title, final_tags_str

        # 3. 日文标题检测
        matched, score = self.check_title_match(clean_name, t_jp, is_strict=is_strict_mode)
        if matched:
            logger.debug(f"✅ [匹配成功] 日文标题")
            return True, final_title, final_tags_str

        # 4. 翻译 Tag 检测
        if self.check_tags_coverage(clean_name, combined_tags):
            logger.debug(f"✅ [匹配成功] 翻译标签覆盖")
            return True, final_title, final_tags_str

        logger.info(f"❌ [匹配失败] 校验不通过 (Mode: {mode})")
        return False, final_title, final_tags_str