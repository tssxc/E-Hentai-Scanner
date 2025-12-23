# app/utils.py
import time
import random
import logging
import re  # 补充缺失的导入
from rapidfuzz import fuzz  # 引入 rapidfuzz
from . import config

logger = logging.getLogger(__name__)

def perform_random_sleep():
    """
    执行随机休眠
    根据 config.py 中的 SLEEP_MIN 和 SLEEP_MAX 进行休眠
    """
    sleep_time = random.uniform(config.SLEEP_MIN, config.SLEEP_MAX)
    logger.debug(f"⏳ [防封禁] 随机休眠 {sleep_time:.2f}s...")
    time.sleep(sleep_time)

def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两个字符串的相似度 (0.0 ~ 1.0)
    使用 rapidfuzz 的 token_sort_ratio 和 token_set_ratio 综合评估。
    """
    if not text1 or not text2:
        return 0.0

    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    if t1 in t2 or t2 in t1:
        logger.debug(f"[Sim] '{t1}' <-> '{t2}' => 1.0 (包含匹配)")
        return 1.0

    score_sort = fuzz.token_sort_ratio(t1, t2)
    score_set = fuzz.token_set_ratio(t1, t2)
    final_score = max(score_sort, score_set) / 100.0
    logger.debug(f"[Sim] '{t1}' <-> '{t2}' => Sort:{score_sort} | Set:{score_set} | Final:{final_score:.2f}")
    return final_score

def parse_gallery_title(full_title: str) -> dict:
    """
    解析 E-Hentai/ExHentai 格式的标题
    """
    info = {
        'event': None,
        'circle': None,
        'artist': None,
        'title': None,
        'parody': None,
        'translation': None,
        'is_dl': False
    }

    logger.debug(f"[parse_gallery_title] 原始输入: '{full_title}'")
    if not full_title:
        logger.debug(f"[parse_gallery_title] 输入为空，返回默认 info: {info}")
        return info

    # 全角转半角
    clean_title = (
        full_title.replace('（', '(').replace('）', ')')
        .replace('【', '[').replace('】', ']')
        .replace('［', '[').replace('］', ']')
    )
    logger.debug(f"[parse_gallery_title] 预处理后标题: '{clean_title}'")

    remaining = clean_title.strip()
    logger.debug(f"[parse_gallery_title] 初始 remaining: '{remaining}'")

    # 提取 (会展)
    event_match = re.match(r'^\(([^)]+)\)', remaining)
    if event_match:
        info['event'] = event_match.group(1).strip()
        logger.debug(f"[parse_gallery_title] 提取到会展: '{info['event']}'")
        remaining = remaining[event_match.end():].strip()
        logger.debug(f"[parse_gallery_title] 去除会展后 remaining: '{remaining}'")

    # 提取 [社团 (作者)]
    circle_match = re.match(r'^\[([^\]]+)\]', remaining)
    if circle_match:
        content = circle_match.group(1).strip()
        logger.debug(f"[parse_gallery_title] 括号内容(社团/作者): '{content}'")
        ca_match = re.search(r'^(.*?)\s*\(([^)]+)\)$', content)
        if ca_match:
            info['circle'] = ca_match.group(1).strip()
            info['artist'] = ca_match.group(2).strip()
            logger.debug(f"[parse_gallery_title] 提取到社团: '{info['circle']}', 作者: '{info['artist']}'")
        else:
            info['circle'] = content
            logger.debug(f"[parse_gallery_title] 仅社团，无作者: '{info['circle']}'")

        remaining = remaining[circle_match.end():].strip()
        logger.debug(f"[parse_gallery_title] 去除社团/作者后 remaining: '{remaining}'")

    # 检测 [DL版]/[DL]
    if '[DL版]' in remaining or '[DL]' in remaining:
        info['is_dl'] = True
        logger.debug(f"[parse_gallery_title] 检测到 DL 标记")
        remaining = remaining.replace('[DL版]', '').replace('[DL]', '').strip()
        logger.debug(f"[parse_gallery_title] 去除 DL 标记后 remaining: '{remaining}'")

    # 提取 [翻译/语言] 标签
    translations = []
    while True:
        end_bracket_match = re.search(r'\[([^\]]+)\]$', remaining)
        if end_bracket_match:
            tag_content = end_bracket_match.group(1).strip()
            translations.insert(0, tag_content)
            logger.debug(f"[parse_gallery_title] 提取到翻译/语言标签: '{tag_content}'")
            remaining = remaining[:end_bracket_match.start()].strip()
            logger.debug(f"[parse_gallery_title] 去除一个翻译/语言标签后 remaining: '{remaining}'")
        else:
            break

    if translations:
        info['translation'] = " ".join(translations)
        logger.debug(f"[parse_gallery_title] 所有翻译/语言标签: '{info['translation']}'")

    # 提取 (类型/原作)
    parody_match = re.search(r'\(([^)]+)\)$', remaining)
    if parody_match:
        info['parody'] = parody_match.group(1).strip()
        logger.debug(f"[parse_gallery_title] 提取到类型/原作: '{info['parody']}'")
        remaining = remaining[:parody_match.start()].strip()
        logger.debug(f"[parse_gallery_title] 去除类型/原作后 remaining: '{remaining}'")

    info['title'] = remaining
    logger.debug(f"[parse_gallery_title] 提取到 title: '{info['title']}'")
    logger.debug(f"[parse_gallery_title] 最终解析结果: {info}")

    return info