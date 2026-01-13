# app/utils.py
import time
import random
import logging
import re
import difflib  # [新增] 必须引入标准库 difflib
from rapidfuzz import fuzz
from . import config

# 强制获取 logger
logger = logging.getLogger(__name__)

def verify_environment():
    """
    环境目录自检 (从 common.py 迁移而来)
    """
    if not config.DATA_DIR.exists():
        logger.info(f"创建数据目录: {config.DATA_DIR}")
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        
    if not config.LOG_DIR.exists():
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
    if not config.UNRAR_PATH.exists():
        logger.warning(f"⚠️ 未找到 UnRAR 工具: {config.UNRAR_PATH}，RAR 文件将无法处理。")
    else:
        logger.debug(f"✅ UnRAR 路径确认: {config.UNRAR_PATH}")


def calculate_similarity(text1: str, text2: str) -> float:# TODO: 删除此函数
    """
    [旧算法] 基于 RapidFuzz 的相似度 (0.0 ~ 1.0)
    保留此函数以兼容旧代码，但建议使用下方的 calculate_hybrid_similarity
    """
    if not text1 or not text2:
        return 0.0

    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    if t1 in t2 or t2 in t1:
        return 1.0

    score_sort = fuzz.token_sort_ratio(t1, t2)
    score_set = fuzz.token_set_ratio(t1, t2)
    final_score = max(score_sort, score_set) / 100.0
    
    return final_score

def parse_gallery_title(full_title: str) -> dict:#TODO: 遍历标题中所有的 [...] 块。
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

# ========================================================
# [新增] 混合相似度算法 (支持中日文分词 + 顺序检测)
# 解决 ImportError: cannot import name 'calculate_hybrid_similarity'
# ========================================================

def cjk_tokenize(text: str) -> list:
    """
    [核心] 针对中日韩+英文混合环境的智能分词
    策略：
    1. 英文/数字：按单词匹配 (如 "Vol.1" -> "vol", "1")
    2. CJK字符：按单字匹配 (如 "海贼王" -> "海", "贼", "王")
    """
    if not text: return []
    text = text.lower()
    
    # 正则逻辑：
    # 1. [a-z0-9]+ : 匹配连续的英文或数字 (英文单词)
    # 2. [^\u0000-\u007F] : 匹配所有非ASCII字符 (中日文字符)
    tokens = re.findall(r'[a-z0-9]+|[^\u0000-\u007F]', text)
    
    return tokens

def calculate_cjk_ordered_score(filename: str, title: str) -> float:
    """
    支持 CJK 的有序序列相似度算法
    """
    if not filename or not title: return 0.0

    # 1. 使用混合分词
    tokens_file = cjk_tokenize(filename)
    tokens_title = cjk_tokenize(title)
    
    if not tokens_file or not tokens_title: return 0.0

    # 2. 序列比对 (要求顺序一致)
    # autojunk=False 关闭自动过滤，对短语比对更准确
    matcher = difflib.SequenceMatcher(None, tokens_file, tokens_title, autojunk=False)
    
    matches = matcher.get_matching_blocks()
    match_count = sum(match.size for match in matches)
    
    # 3. 计算得分 (分母为文件名单词数)
    return match_count / len(tokens_file)

def calculate_hybrid_similarity(filename: str, title: str) -> float:
    """
    [综合入口] 结合 字符匹配 和 智能分词匹配
    该函数被 app/validator.py 调用
    """
    if not filename or not title: return 0.0
    
    # A. 连续字符匹配 (适合极短文件名，或纯数字 "01.zip")
    score_char = difflib.SequenceMatcher(None, filename.lower(), title.lower()).ratio()
    
    # B. CJK智能分词匹配 (适合语义包含 "海贼王" in "[汉化] 海贼王")
    score_token = calculate_cjk_ordered_score(filename, title)
    
    # 长度保护：如果文件名太短(少于2个字/词)，强制使用字符匹配
    # 防止单个字(如"王")匹配到任何包含该字的标题
    if len(filename) < 2:
        return score_char
        
    return max(score_char, score_token)