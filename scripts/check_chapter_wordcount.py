#!/usr/bin/env python3
"""检查中文正文成稿的 AI 味硬禁令与统计形态 + 章节字数校验。只报警，不自动改文。
移植自 human-writing skill 的 scripts/check_prose.py
（MIT License, Copyright (c) 2026 Human Writing Skill contributors），
按本项目 knowledge/anti-ai/common-rules.md 口径调整：
- 冒号不检查（网文无此禁令）；
- 破折号不做硬禁，段落内 ≥3 处时提示逐处按用法判定（common-rules.md 破折号判定）；
- 段落按行切分（网文章节每段一行，空行仅作分隔）。

变更说明：
  1. warnings 同样触发返回码1；failures/warnings任意非空即视为不通过
  2. --min-words 默认值改为 2000
  3. --word‑check      开启章节字数校验，不足归入 failures 硬错误
  4. --min-words N     章节最低汉字数，默认2000，配合--word‑check
  5. --all DIR         批量扫描目录下 第*.md 章节文件
  6. --json            输出机器可读JSON，适合CI/Agent调用

用法:
# 单文件，仅AI文风检查
python3 check-prose.py <稿件路径|->

# 单文件，AI文风 + 字数硬校验
python3 check-prose.py --word-check <稿件路径> [--min-words 2000]

# 批量目录全部章节
python3 check-prose.py --all novels/chapters --word-check --min-words 2000

# JSON输出
python3 check-prose.py --all novels/chapters --word-check --json

退出码:
0 = 全部无 failures、无 warnings
1 = 存在 failures OR 存在 warnings OR 章节字数不足
2 = 读取失败 / 参数错误
"""
from __future__ import annotations
import argparse
import collections
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

HARD_STOPS = (
    "说白了",
    "说穿了",
    "先说结论",
    "她说",
    "他说",
)
HARD_JARGON = (
    "赋能",
    "抓手",
    "商业闭环",
    "价值闭环",
    "能力沉淀",
    "拉通",
    "底层逻辑",
    "顶层设计",
    "认知跃迁",
    "价值释放",
    "能力建设",
    "降本增效",
    "内容矩阵",
    "全链路",
    "组合拳",
    "打开想象空间",
    "结构性机会",
    "关键命题",
    "深层逻辑",
    "技术底座",
    "公共底座",
    "技术主权",
    "单点风险",
    "主脊柱",
    "材料锚点",
    "认知增量",
    "迭代闭环",
)
CONTEXT_JARGON = (
    "沉淀",
    "颗粒度",
    "对齐",
    "协同",
    "链路",
    "生态位",
    "心智",
    "范式",
    "方法论",
    "核心变量",
    "打法",
    "想象空间",
    "闭环",
    "不丢",
)
LYRIC_WORDS = (
    "安放",
    "抵达",
    "微光",
    "褶皱",
    "丰盈",
    "滚烫",
    "轻盈",
    "赤裸",
    "剥开",
)
ROAD_SIGNS = (
    "更微妙的是",
    "还有一层",
    "只说对了一半",
    "值得注意的是",
    "需要指出的是",
    "从某种意义上说",
)
ROAD_STRIP_CHARS = "。！？!? \n"
DASH_OCCURRENCE = re.compile(r"——|—|–")
PIVOT_PATTERNS = (
    re.compile(r"(?:并)?不是[^。！？\n]{0,90}而是"),
    re.compile(r"并非[^。！？\n]{0,90}而是"),
    re.compile(r"不在于[^。！？\n]{0,90}而在于"),
    re.compile(r"与其说[^。！？\n]{0,90}(?:不如|毋宁|倒不如)"),
    re.compile(r"[。！？!?]\s*而是"),
    re.compile(r"表面(?:上)?[^。！？\n]{0,90}(?:其实|实际|实则)"),
    re.compile(r"看似[^。！？\n]{0,90}(?:其实|实际|实则)"),
)
SEMANTIC_PIVOT_PATTERNS = (
    re.compile(r"(?:总|一直|曾|都)?以为[^！？\n]{2,60}?(?:其实|才发现|才明白|才知道|后来才)"),
    re.compile(r"(?:总|都|一直)以为[^！？\n]{2,60}?[。，](?:可|但|其实)"),
    re.compile(r"回头(?:看|一看)?才(?:发现|明白|知道)"),
    re.compile(r"(?:并)?不是[^。！？\n]{1,40}，(?:更|才)?是[^，。！？\n]"),
    re.compile(r"从来(?:都)?(?:不是|与[^。！？，\n]{1,12}无关)"),
    re.compile(r"答案(?:是否定的|恰恰相反)|恰恰相反"),
    re.compile(r"表面(?:上)?[^！？\n]{0,60}。[^！？\n]{0,12}(?:其实|实际|实则)"),
    re.compile(r"看似[^！？\n]{0,60}。[^！？\n]{0,12}(?:其实|实际|实则)"),
    re.compile(r"[^，。！？\n]{1,12}不重要，(?:重要|要紧)的是"),
    re.compile(r"真正[^，。！？\n]{0,16}的(?:，)?是"),
    re.compile(r"不只(?:是)?[^。！？\n]{0,90}(?:还|也)"),
)
NOMINALIZATION_PATTERNS = (
    re.compile(r"进行(?:了|一次|一场|着)?[^。，！？\n]{0,10}(?:调整|优化|升级|分析|讨论|沟通|梳理|复盘|迭代|探索|尝试|思考|规划|布局)"),
    re.compile(r"实现了?[^。，！？\n]{0,14}的?[^。，！？\n]{0,6}(?:提升|增长|突破|转变|跃升|落地)"),
    re.compile(r"完成了?对[^。，！？\n]{0,16}的"),
    re.compile(r"起到了?[^。，！？\n]{0,12}的?作用"),
    re.compile(r"具有[^。，！？\n]{0,10}(?:意义|价值)"),
)
CONJUNCTIONS = (
    "因为",
    "所以",
    "但是",
    "然而",
    "同时",
    "此外",
    "而且",
    "并且",
    "因此",
    "不仅",
)
ROAD_SIGN_PATTERNS = (
    re.compile(
        rf"(?:^|[。！？!?]\s*){re.escape(ROAD_SIGNS[0])}[^。！？!?\n]{{0,24}}",
        re.MULTILINE,
    ),
    re.compile(
        rf"(?:^|[。！？!?]\s*){re.escape(ROAD_SIGNS[1])}(?=(?:更|原因|问题|意思|考虑|变化|逻辑|价值|作用|风险|影响|值得|很少|不容易|常被|往往))[^。！？!?\n]{{0,24}}",
        re.MULTILINE,
    ),
    *(
        re.compile(
            rf"(?:^|[。！？!?]\s*){re.escape(phrase)}[^。！？!?\n]{{0,24}}",
            re.MULTILINE,
        )
        for phrase in ROAD_SIGNS[2:]
    ),
)
SOFT_MARKERS = (
    "真正",
    "本质上",
    "更深层次",
    "归根结底",
    "换句话说",
    "不可否认",
    "核心是",
    "关键在于",
    "这意味着",
)
REPEATED_OPENERS = (
    "其实",
    "不过",
    "当然",
    "所以",
    "但是",
    "后来",
    "当时",
    "很多人",
    "问题是",
    "更重要的是",
    "说到这里",
)
LEFT_BRANCH_PATTERNS = (
    re.compile(r"(?:^|[。！？]\s*)在[^，。！？\n]{12,70}(?:以后|之后|之前|以前|过程中|情况下|背景下)，"),
    re.compile(r"(?:^|[。！？]\s*)那些[^，。！？\n]{10,60}的[^，。！？\n]{2,30}[，。]"),
    re.compile(r"(?:^|[。！？]\s*)(?:真正|最终|最后)让[^，。！？\n]{8,70}的，是"),
)
METAPHOR_FIELDS = {
    "温度": ("降温", "升温", "冷却", "余温", "温度最高"),
    "生死战争": ("杀死", "死因", "枪响", "开火", "战场", "引爆", "弹药"),
    "建筑灾害": ("坍塌", "崩塌", "地基", "砖头", "支柱", "废墟"),
    "仓储租赁": ("仓库", "库房", "租金", "取货", "入库", "库存"),
    "道路竞赛": ("赛道", "跑道", "岔路", "十字路口", "终点线", "门票"),
    "机器器官": ("齿轮", "引擎", "发动机", "血管", "骨架", "肌肉"),
    "海洋航行": ("蓝海", "浪潮", "潮水", "航船", "灯塔", "彼岸"),
}

@dataclass
class Paragraph:
    position: int
    text: str
    han: int
    sentences: int


def han_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def excerpt(value: str, width: int = 72) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= width else value[: width - 1] + "…"


def mask_non_prose(text: str) -> str:
    def mask(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group())
    patterns = (
        re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", re.DOTALL),
        re.compile(r"```.*?```", re.DOTALL),
        re.compile(r"`[^`\n]*`"),
        re.compile(r"\]\([^\n)]*\)"),
        re.compile(r"https?://[^\s)>]+"),
        re.compile(r"<[^>\n]+>"),
    )
    masked = text
    for pattern in patterns:
        masked = pattern.sub(mask, masked)
    return masked


def non_overlapping_terms(text: str, terms: tuple[str, ...]):
    matches = []
    occupied = []
    for term in sorted(terms, key=len, reverse=True):
        for match in re.finditer(re.escape(term), text):
            start, end = match.span()
            if any(start < old_end and end > old_start for old_start, old_end in occupied):
                continue
            matches.append((start, term))
            occupied.append((start, end))
    return sorted(matches)


def all_matches(text: str, patterns: tuple[re.Pattern[str], ...]):
    matches = []
    for pattern in patterns:
        matches.extend(pattern.finditer(text))
    return sorted(matches, key=lambda match: match.start())


def heavy_de_sentences(text: str):
    matches = []
    pattern = re.compile(r"[^。！？!?\n]+(?:[。！？!?]|$)")
    for match in pattern.finditer(text):
        value = match.group()
        if han_count(value) >= 38 and value.count("的") >= 4:
            matches.append(match)
    return matches


def anaphora_runs(text: str, minimum: int = 3):
    matches = []
    for sentence in re.finditer(r"[^。！？!?\n]+(?:[。！？!?]|$)", text):
        clauses = [
            clause.strip()
            for clause in re.split(r"[，、；,;]", sentence.group())
            if han_count(clause) >= 3
        ]
        if len(clauses) < minimum:
            continue
        run = 1
        for previous, current in zip(clauses, clauses[1:]):
            if previous[:2] == current[:2] and re.match(r"[一-鿿]{2}", current):
                run += 1
                if run >= minimum:
                    matches.append(sentence)
                    break
            else:
                run = 1
    return matches


def sentence_length_cv(text: str):
    lengths = [
        han_count(match.group())
        for match in re.finditer(r"[^。！？!?\n]+[。！？!?]", text)
        if han_count(match.group()) >= 4
    ]
    if len(lengths) < 12:
        return None
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return None
    variance = sum((value - mean) ** 2 for value in lengths) / len(lengths)
    return (variance ** 0.5) / mean, len(lengths)


def bracket_highlights(text: str):
    return list(re.finditer(r"[「『][^」』\n]{1,6}[」』]", text))


def prose_paragraphs(text: str) -> list[Paragraph]:
    paragraphs = []
    position = 0
    for line in text.splitlines():
        start = position
        position += len(line) + 1
        clean = re.sub(r"[>*_`]", "", line).strip()
        if not clean or clean.startswith(("#", "http", "![", "```")):
            continue
        if re.match(r"^(?:[-+*]|\d+[.、])\s", clean):
            continue
        count = han_count(clean)
        if count < 4:
            continue
        sentences = max(1, len(re.findall(r"[。！？!?]", clean)))
        paragraphs.append(Paragraph(start, clean, count, sentences))
    return paragraphs


def metaphor_cluster(text: str, distance: int = 800):
    hits = []
    for field, words in METAPHOR_FIELDS.items():
        for word in words:
            for match in re.finditer(re.escape(word), text):
                hits.append((match.start(), field, word))
    hits.sort()
    for index, (start, _, _) in enumerate(hits):
        window = [hit for hit in hits[index:] if hit[0] - start <= distance]
        fields = {hit[1] for hit in window}
        if len(fields) >= 3:
            return window, fields
    return None


def short_streak(paragraphs: list[Paragraph], limit: int = 4):
    streak = []
    for paragraph in paragraphs:
        if paragraph.han <= 24 and paragraph.sentences <= 1:
            streak.append(paragraph)
            if len(streak) >= limit:
                return streak
        else:
            streak = []
    return None


def opener_counts(paragraphs: list[Paragraph]):
    counts = collections.Counter()
    examples = {}
    for paragraph in paragraphs:
        value = paragraph.text.lstrip("“‘\"（(")
        for opener in REPEATED_OPENERS:
            if value.startswith(opener):
                counts[opener] += 1
                examples.setdefault(opener, paragraph.position)
                break
    return counts, examples


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


# ---------- 字数统计工具 ----------
def count_chinese_words(text: str) -> int:
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars)


def extract_content_from_chapter(full_text: str) -> str:
    lines = full_text.split('\n')
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith('#') and '章' in line:
            content_start = i + 1
            break
    main_content = '\n'.join(lines[content_start:])
    return main_content


def chapter_sort_key(path: Path):
    m = re.search(r'第(\d+)章', path.name)
    return (int(m.group(1)) if m else 9999, path.name)


def scan_single_file(text: str, source_text: str, word_check: bool, min_words: int):
    """
    对一份文本执行全部检测
    :param text: mask_non_prose后的文本
    :param source_text: 原始完整文本（用于取行号）
    :param word_check: 是否开启字数校验
    :param min_words: 最低字数
    :return: dict failures, warnings, metrics, chapter_word_count
    """
    failures = []
    warnings = []
    chapter_word_count = None

    total_han = han_count(text)

    # --- 字数校验（不足归入 failures 硬错误）
    if word_check:
        chapter_body = extract_content_from_chapter(source_text)
        chapter_word_count = count_chinese_words(chapter_body)
        if chapter_word_count < min_words:
            failures.append(f"【章节字数不足】正文汉字 {chapter_word_count}，要求最少 {min_words}")

    stop_matches = non_overlapping_terms(text, HARD_STOPS)
    for position, phrase in stop_matches:
        failures.append(f"硬停词，第 {line_number(source_text, position)} 行，{phrase}")

    jargon_matches = non_overlapping_terms(text, HARD_JARGON)
    for position, phrase in jargon_matches:
        failures.append(f"黑话，第 {line_number(source_text, position)} 行，{phrase}")

    context_jargon_matches = non_overlapping_terms(text, CONTEXT_JARGON)
    hard_spans = [(position, position + len(phrase)) for position, phrase in jargon_matches]
    context_jargon_matches = [
        (pos, ph) for pos, ph in context_jargon_matches
        if not any(pos < e and pos + len(ph) > s for s, e in hard_spans)
    ]
    if context_jargon_matches:
        samples = "、".join(dict.fromkeys(ph for _, ph in context_jargon_matches))
        lines = "、".join(dict.fromkeys(str(line_number(source_text, p)) for p, _ in context_jargon_matches[:8]))
        warnings.append(
            f"有 {len(context_jargon_matches)} 处词语需要结合语境判断。"
            f"第 {lines} 行出现 {samples}。本义准确时保留，用来抬价时改写。"
        )

    road_signs = all_matches(text, ROAD_SIGN_PATTERNS)
    for match in road_signs:
        failures.append(
            f"模型路标，第 {line_number(source_text, match.start())} 行，"
            f"“{excerpt(match.group().lstrip(ROAD_STRIP_CHARS))}”"
        )

    pivots = all_matches(text, PIVOT_PATTERNS)
    for match in pivots:
        failures.append(
            f"禁用翻案句，第 {line_number(source_text, match.start())} 行，"
            f"“{excerpt(match.group())}”"
        )

    occupied_spans = [m.span() for m in pivots]
    semantic_pivots = []
    for match in all_matches(text, SEMANTIC_PIVOT_PATTERNS):
        if any(match.start() < e and match.end() > s for s, e in occupied_spans):
            continue
        semantic_pivots.append(match)
        occupied_spans.append(match.span())
    for match in semantic_pivots:
        warnings.append(
            f"疑似翻案腔变形，第 {line_number(source_text, match.start())} 行，"
            f"“{excerpt(match.group(), 44)}”。先立误解再推翻就改成正面陈述，正常用法保留。"
        )

    anaphoras = anaphora_runs(text)
    for match in anaphoras[:4]:
        warnings.append(
            f"三连以上同构排比，第 {line_number(source_text, match.start())} 行，"
            f"“{excerpt(match.group(), 44)}”。留两项，第三项换说法或删掉。"
        )

    lyric_matches = non_overlapping_terms(text, LYRIC_WORDS)
    if len(lyric_matches) >= 2:
        samples = "、".join(dict.fromkeys(t for _, t in lyric_matches))
        warnings.append(
            f"模型偏爱的抒情词 {len(lyric_matches)} 处。{samples}。"
            "写具体事物时保留，给抽象概念穿衣服时删掉。"
        )

    nominalizations = all_matches(text, NOMINALIZATION_PATTERNS)
    for match in nominalizations[:4]:
        warnings.append(
            f"名词化句式，第 {line_number(source_text, match.start())} 行，"
            f"“{excerpt(match.group(), 36)}”。还原成直接的动词。"
        )

    conjunction_hits = non_overlapping_terms(text, CONJUNCTIONS)
    if total_han >= 600 and len(conjunction_hits) * 1000 / total_han > 7:
        samples = "、".join(f"{term} {cnt} 次" for term, cnt in collections.Counter(t for _, t in conjunction_hits).most_common(4))
        warnings.append(
            f"连词密度偏高，每千字 {len(conjunction_hits) * 1000 // total_han} 个。{samples}。"
            "中文小句靠语序和事理相接，删掉一半试试。"
        )

    highlights = bracket_highlights(text)
    highlight_limit = max(3, total_han // 700)
    if len(highlights) > highlight_limit:
        samples = "、".join(dict.fromkeys(m.group() for m in highlights[:6]))
        warnings.append(
            f"「」括起的短语共 {len(highlights)} 处。{samples}。太密说明在批量造金句。"
        )

    cv_result = sentence_length_cv(text)
    if cv_result and cv_result[0] < 0.42:
        warnings.append(
            f"全文 {cv_result[1]} 个句子长度过于接近（变异系数 {cv_result[0]:.2f}）。"
            "人写的段落里十个字的句子会挨着四十个字的句子，放开几句，压短几句。"
        )

    marker_matches = non_overlapping_terms(text, SOFT_MARKERS)
    marker_limit = max(2, total_han // 900)
    if len(marker_matches) > marker_limit:
        samples = "、".join(dict.fromkeys(t for _, t in marker_matches))
        warnings.append(
            f"洞察路标共 {len(marker_matches)} 处，当前提醒线为 {marker_limit} 处。重点检查 {samples}。"
        )

    left_branches = all_matches(text, LEFT_BRANCH_PATTERNS)
    left_limit = max(2, total_han // 1200)
    if len(left_branches) > left_limit:
        samples = "；".join(f"第 {line_number(source_text, m.start())} 行“{excerpt(m.group(),44)}”" for m in left_branches[:4])
        warnings.append(f"长前置成分共 {len(left_branches)} 处，可能让主干来得太晚。{samples}")

    dense_de = heavy_de_sentences(text)
    dense_de_limit = max(1, total_han // 1500)
    if len(dense_de) > dense_de_limit:
        samples = "；".join(f"第 {line_number(source_text, m.start())} 行“{excerpt(m.group(),44)}”" for m in dense_de[:4])
        warnings.append(f"有 {len(dense_de)} 个长句包含四个以上的“的”，可能要先交代人和动作。{samples}")

    paragraphs = prose_paragraphs(text)
    dash_dense_paragraphs = 0
    for para in paragraphs:
        dash_cnt = len(DASH_OCCURRENCE.findall(para.text))
        if dash_cnt >=3:
            dash_dense_paragraphs +=1
            warnings.append(
                f"第 {line_number(source_text, para.position)} 行段落内破折号 {dash_cnt} 处，"
                "逐处按用法判定：删掉破折号及两侧内容后意思不变则删。"
            )

    if len(paragraphs)>=10:
        one_sentence = sum(p.sentences <=1 for p in paragraphs)
        ratio = one_sentence / len(paragraphs)
        if ratio >=0.75:
            warnings.append(f"可识别段落中有 {ratio:.0%} 只有一句话，可能形成统一的短段鼓点。")

    streak = short_streak(paragraphs)
    if streak:
        first = streak[0]
        warnings.append(
            f"从第 {line_number(source_text, first.position)} 行起连续出现 {len(streak)} 个短促单句段，检查是否在排队喊结论。"
        )

    counts, opener_examples = opener_counts(paragraphs)
    repeated = [(op, c) for op,c in counts.items() if c >=4]
    if repeated:
        details = "、".join(f"{op} {c} 次" for op,c in repeated)
        first_pos = min(opener_examples[op] for op,_ in repeated)
        warnings.append(f"段落开场重复，从第 {line_number(source_text, first_pos)} 行附近开始。{details}。")

    metaphors = metaphor_cluster(text)
    if metaphors:
        window, fields = metaphors
        samples = "、".join(dict.fromkeys(h[2] for h in window))
        warnings.append(
            f"八百字内出现 {len(fields)} 套借喻。{'、'.join(sorted(fields))}。例词有 {samples}。"
        )

    metrics = {
        "total_han": total_han,
        "pivots": len(pivots),
        "semantic_pivots": len(semantic_pivots),
        "anaphoras": len(anaphoras),
        "nominalizations": len(nominalizations),
        "jargon_matches": len(jargon_matches),
        "stop_matches": len(stop_matches),
        "road_signs": len(road_signs),
        "context_jargon_matches": len(context_jargon_matches),
        "lyric_matches": len(lyric_matches),
        "marker_matches": len(marker_matches),
        "left_branches": len(left_branches),
        "dense_de": len(dense_de),
        "dash_dense_paragraphs": dash_dense_paragraphs,
    }
    return {
        "failures": failures,
        "warnings": warnings,
        "metrics": metrics,
        "chapter_word_count": chapter_word_count
    }


def human_print_one(filepath: str, res: dict):
    print(f"\n===== 文件：{filepath} =====")
    m = res["metrics"]
    print(f"汉字数 {m['total_han']}")
    print(
        f"翻案句 {m['pivots']}，翻案腔变形 {m['semantic_pivots']}，"
        f"同构排比 {m['anaphoras']}，名词化 {m['nominalizations']}，"
        f"黑话 {m['jargon_matches']}，高频用词 {m['stop_matches']}，"
        f"模型路标 {m['road_signs']}，需辨语境词 {m['context_jargon_matches']}，"
        f"抒情词 {m['lyric_matches']}，洞察路标 {m['marker_matches']}，"
        f"长前置成分 {m['left_branches']}，重定语句 {m['dense_de']}，"
        f"破折号密集段 {m['dash_dense_paragraphs']}"
    )
    if res["failures"]:
        print("\n❌ 硬错误（必须修改）")
        for item in res["failures"]:
            print(f"- {item}")
    if res["warnings"]:
        print("\n⚠️  警告（现在同样视为不通过，必须修改）")
        for item in res["warnings"]:
            print(f"- {item}")
    if not res["failures"] and not res["warnings"]:
        print("\n✅ 未发现问题")


def main() -> int:
    parser = argparse.ArgumentParser(description="AI文风检查 + 章节字数校验")
    parser.add_argument("path", nargs='?', help="文件路径；--all模式不需要此参数，单文件时必填；'-'为stdin")
    parser.add_argument("--all", metavar="DIR", help="批量扫描目录，匹配 第*.md")
    parser.add_argument("--word-check", action="store_true", help="开启章节字数校验，不足归入硬错误failures")
    parser.add_argument("--min-words", type=int, default=2000, help="最低章节汉字数，默认2000")
    parser.add_argument("--json", action="store_true", help="输出JSON，关闭人类打印")
    args = parser.parse_args()

    # 校验参数
    if args.all:
        if args.path is not None:
            parser.error("--all模式不要提供位置path参数，直接写目录到--all后面")
        dir_p = Path(args.all)
        if not dir_p.exists():
            if args.json:
                print(json.dumps({"error": f"目录不存在: {args.all}"}, ensure_ascii=False))
            else:
                print(f"目录不存在: {args.all}", file=sys.stderr)
            return 2
        if not dir_p.is_dir():
            if args.json:
                print(json.dumps({"error": f"不是目录: {args.all}"}, ensure_ascii=False))
            else:
                print(f"不是目录: {args.all}", file=sys.stderr)
            return 2
        files = sorted(dir_p.glob("第*.md"), key=chapter_sort_key)
        if not files:
            if args.json:
                print(json.dumps({"error": f"目录 {args.all} 未找到第*.md章节文件"}, ensure_ascii=False))
            else:
                print(f"目录 {args.all} 未找到第*.md章节文件", file=sys.stderr)
            return 2
        file_list: list[Path | str] = files
    else:
        if args.path is None:
            parser.error("单文件模式必须提供path参数，或者使用--all <目录>")
        file_list = [args.path]

    overall_has_failure = False
    per_file_results = []

    for fp in file_list:
        fp_str = str(fp)
        try:
            raw_text = read_text(fp_str)
        except (OSError, UnicodeError) as e:
            err_rec = {
                "file": fp_str,
                "error": str(e),
                "failures": [],
                "warnings": [],
                "metrics": None,
                "chapter_word_count": None
            }
            per_file_results.append(err_rec)
            overall_has_failure = True
            continue

        prose = mask_non_prose(raw_text)
        if han_count(prose) == 0:
            rec = {
                "file": fp_str,
                "error": "没有检测到汉字",
                "failures": [],
                "warnings": [],
                "metrics": None,
                "chapter_word_count": None
            }
            per_file_results.append(rec)
            overall_has_failure = True
            continue

        r = scan_single_file(prose, raw_text, word_check=args.word_check, min_words=args.min_words)
        rec = {
            "file": fp_str,
            "error": None,
            "failures": r["failures"],
            "warnings": r["warnings"],
            "metrics": r["metrics"],
            "chapter_word_count": r["chapter_word_count"]
        }
        per_file_results.append(rec)
        # ========== 关键修改：failures 或者 warnings 任意不为空，整体标记失败 ==========
        if len(r["failures"]) > 0 or len(r["warnings"]) > 0:
            overall_has_failure = True
        if not args.json:
            human_print_one(fp_str, r)

    out_json = {
        "summary": {
            "total_files": len(per_file_results),
            "has_any_failure": overall_has_failure,
        },
        "files": per_file_results
    }
    if args.json:
        print(json.dumps(out_json, ensure_ascii=False, indent=2))

    if overall_has_failure:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
