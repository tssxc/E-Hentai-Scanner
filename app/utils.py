# app/utils.py
import time
import random
import logging
import re
from rapidfuzz import fuzz
from . import config

# 强制获取 logger，防止未初始化
logger = logging.getLogger(__name__)

def perform_random_sleep():
    """执行随机休眠"""
    sleep_time = random.uniform(config.SLEEP_MIN, config.SLEEP_MAX)
    # logger.debug(f"⏳ [防封禁] 随机休眠 {sleep_time:.2f}s...")
    time.sleep(sleep_time)

def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两个字符串的相似度 (0.0 ~ 1.0)
    """
    # ⚠️ 1. 增加：空值检查的日志，防止静默失败
    if not text1 or not text2:
        logger.debug(f"⚠️ [Sim-Skip] 跳过对比 (空值): Local='{text1}' vs Remote='{text2}'")
        return 0.0

    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    # ⚠️ 2. 增加：包含匹配的日志
    if t1 in t2 or t2 in t1:
        logger.debug(f"✅ [Sim-Direct] '{t1}' <-> '{t2}' => 1.0 (包含)")
        return 1.0

    score_sort = fuzz.token_sort_ratio(t1, t2)
    score_set = fuzz.token_set_ratio(t1, t2)
    final_score = max(score_sort, score_set) / 100.0
    
    # ⚠️ 3. 正常计算的日志
    logger.debug(f"🆚 [Sim-Calc] '{t1}' <-> '{t2}' => Sort:{score_sort} | Set:{score_set} | Final:{final_score:.2f}")
    return final_score

def parse_gallery_title(full_title: str) -> dict:
    """解析 E-Hentai/ExHentai 格式的标题"""
    info = {
        'event': None, 'group': None, 'artist': None,
        'title': None, 'parody': None, 'translation': None, 'is_dl': False
    }

    if not full_title:
        return info

    clean_title = (
        full_title.replace('（', '(').replace('）', ')')
        .replace('【', '[').replace('】', ']')
        .replace('［', '[').replace('］', ']')
    )

    remaining = clean_title.strip()

    # 提取 (会展)
    event_match = re.match(r'^\(([^)]+)\)', remaining)
    if event_match:
        info['event'] = event_match.group(1).strip()
        remaining = remaining[event_match.end():].strip()

    # 提取 [社团 (作者)]
    circle_match = re.match(r'^\[([^\]]+)\]', remaining)
    if circle_match:
        content = circle_match.group(1).strip()
        ca_match = re.search(r'^(.*?)\s*\(([^)]+)\)$', content)
        if ca_match:
            info['group'] = ca_match.group(1).strip()
            info['artist'] = ca_match.group(2).strip()
        else:
            info['group'] = content
        remaining = remaining[circle_match.end():].strip()

    # 检测 [DL版]
    if '[DL版]' in remaining or '[DL]' in remaining:
        info['is_dl'] = True
        remaining = remaining.replace('[DL版]', '').replace('[DL]', '').strip()

    # 提取 [翻译/语言]
    translations = []
    while True:
        end_bracket_match = re.search(r'\[([^\]]+)\]$', remaining)
        if end_bracket_match:
            tag_content = end_bracket_match.group(1).strip()
            translations.insert(0, tag_content)
            remaining = remaining[:end_bracket_match.start()].strip()
        else:
            break
    if translations:
        info['translation'] = " ".join(translations)

    # 提取 (类型/原作)
    parody_match = re.search(r'\(([^)]+)\)$', remaining)
    if parody_match:
        info['parody'] = parody_match.group(1).strip()
        remaining = remaining[:parody_match.start()].strip()

    info['title'] = remaining
    return info