#!/usr/bin/env python3
"""Step 6 自检 Python 验证器 —— 把 SKILL.md 的软约束变成硬约束。

用法:
    python testcase-skills/生成/scripts/step6_validator.py output/模块名_testcases.md

检查项（对应 SKILL.md Step 6 的 6 项检查）:
    1. 测试点格式 —— 消灭「系统支持/需要通过」等无效句式
    2. 边界值 —— 每个 PRD 阈值有 trio（N-1/N/N+1）
    3. PRD 覆盖 —— 追溯表每行有用例编号
    4. 核心流程结构 —— 流程编号连续（F-01, F-02...）
    5. 通用覆盖矩阵 —— A~I 触发行无空白
    6. 交付标准 —— 评审表完整、编号无重复、P0 占比合理

退出码:
    0 = 全部通过
    1 = 有 P0 问题（阻塞发布）
    2 = 有 P1 问题（建议修复）
    3 = 有 P2 问题（建议优化）
"""

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


# ============================================================
# 问题等级
# ============================================================

@dataclass
class Issue:
    level: str  # P0=阻塞, P1=建议修复, P2=建议优化
    category: str
    message: str


@dataclass
class ValidationResult:
    issues: list = field(default_factory=list)

    @property
    def has_p0(self):
        return any(i.level == "P0" for i in self.issues)

    @property
    def has_p1(self):
        return any(i.level == "P1" for i in self.issues)

    @property
    def has_p2(self):
        return any(i.level == "P2" for i in self.issues)

    @property
    def exit_code(self):
        if self.has_p0:
            return 1
        if self.has_p1:
            return 2
        if self.has_p2:
            return 3
        return 0

    def add(self, level, category, message):
        self.issues.append(Issue(level, category, message))

    def summary(self):
        p0 = [i for i in self.issues if i.level == "P0"]
        p1 = [i for i in self.issues if i.level == "P1"]
        p2 = [i for i in self.issues if i.level == "P2"]
        lines = [
            f"P0 阻塞: {len(p0)}  |  P1 建议: {len(p1)}  |  P2 优化: {len(p2)}",
        ]
        if p0:
            lines.append("")
            lines.append("=== P0 阻塞发布 ===")
            for i in p0:
                lines.append(f"  [{i.category}] {i.message}")
        if p1:
            lines.append("")
            lines.append("=== P1 建议修复 ===")
            for i in p1:
                lines.append(f"  [{i.category}] {i.message}")
        if p2:
            lines.append("")
            lines.append("=== P2 建议优化 ===")
            for i in p2:
                lines.append(f"  [{i.category}] {i.message}")
        return "\n".join(lines)


# ============================================================
# 检查 1: 测试点格式
# ============================================================

# 无效句式正则 —— 这些句式只描述功能，不描述可验证行为
INVALID_PATTERNS = [
    (r"系统支持[。、，;；\s]", "功能描述：「系统支持」应改为「验证...」"),
    (r"支持[。、，;；\s]", "功能描述：「支持」应改为「验证...」"),
    (r"需要通过\s+JWT", "实现细节：「需要通过 JWT 登录」应改为「未带 Token 调用返回 401」"),
    (r"使用\s+Redis\s+扣库存", "实现细节：「使用 Redis 扣库存」应改为「并发下单仅 1 单成功」"),
    (r"活动状态为进行中才可下单", "需求复述：应改为「UPCOMING 时 POST 下单返回约定错误码」"),
    (r"输入合法数据", "模糊：应写具体值，如 username=`buyer01`"),
    (r"操作成功", "模糊：应写 HTTP 状态码/订单 status/库存值"),
    (r"当前时间\s*[=为]", "时间条件当操作：应写 admin 造活动(start=now()+2s)+sleep+POST+4xx，见 time_and_state.md §1.1"),
    (r"拒绝下单[（(]活动未开始", "模糊预期：应写 HTTP 4xx + body 错误码/文案 + 无 order_id"),
]


def check_test_point_format(content: str, result: ValidationResult):
    """检查 1: 测试点格式 —— 消灭无效句式"""
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        # 跳过标题行和表格行
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("|"):
            continue
        for pattern, msg in INVALID_PATTERNS:
            if re.search(pattern, line):
                result.add(
                    "P0",
                    "检查1-格式",
                    f"行 {i}: {msg} | 原文: {stripped[:80]}",
                )


# ============================================================
# 检查 2: 边界值
# ============================================================

# 匹配 PRD 中的数值阈值（排除标题、版本号、层级等）
THRESHOLD_PATTERN = re.compile(
    r"(?:^|[^vV\d\w])(\d+)\s*(?:次|个|条|字节|KB|MB|GB|分钟|小时|天|元|件|人)\b",
    re.MULTILINE,
)

# 匹配 trio 关键词
TRIO_PATTERNS = [
    re.compile(r"(?:\d+\s*[-–]\s*1|\d+\s*[±]\s*1|N[±]1|N-1|N\+1)"),
    re.compile(r"(?:min-1|min|min\+1|max-1|max|max\+1)"),
]


def check_boundary_values(content: str, result: ValidationResult):
    """检查 2: 边界值 —— 每个 PRD 阈值有 trio"""
    # 跳过元数据区域（其中的数量不是 PRD 阈值）
    skip_sections = list(re.finditer(
        r"##\s*(?:文档信息|知识库检索摘要)\s*\n(.*?)(?=##\s|\Z)", content, re.DOTALL
    ))
    # 反向删除，避免位置偏移
    body = content
    for section in reversed(skip_sections):
        body = body[:section.start()] + body[section.end():]

    # 提取 PRD 中的数值阈值
    thresholds = THRESHOLD_PATTERN.findall(body)

    if not thresholds:
        result.add("P2", "检查2-边界", "未检测到 PRD 数值阈值，跳过边界检查")
        return

    # 检查文档中是否有 trio 相关表述
    has_trio = any(p.search(content) for p in TRIO_PATTERNS)

    if not has_trio:
        result.add(
            "P1",
            "检查2-边界",
            f"检测到 {len(thresholds)} 个 PRD 阈值 ({', '.join(set(thresholds))})，"
            f"但文档中未检测到 trio 边界值表述（N-1/N/N+1）",
        )
    else:
        result.add(
            "P2",
            "检查2-边界",
            f"检测到 {len(set(thresholds))} 个 PRD 阈值，"
            f"文档包含 trio 边界值表述",
        )


# ============================================================
# 检查 3: PRD 覆盖 —— 追溯表
# ============================================================

CASE_ID_PATTERN = re.compile(r"[FLDCUXVPN T]-\d{2,}")


def check_prd_coverage(content: str, result: ValidationResult):
    """检查 3: PRD 覆盖 —— 追溯表每行有用例编号"""
    # 找追溯表
    trace_section = re.search(
        r"##\s*需求追溯表\s*\n(.*?)(?=##\s|\Z)", content, re.DOTALL
    )
    if not trace_section:
        result.add("P0", "检查3-覆盖", "未找到「需求追溯表」章节")
        return

    trace_table = trace_section.group(1)
    # 提取表格行（跳过表头、分隔线、空行）
    header_skipped = False
    rows = []
    for r in trace_table.split("\n"):
        stripped = r.strip()
        if not stripped.startswith("|"):
            continue
        # 跳过第一行（表头）和分隔线
        if not header_skipped:
            header_skipped = True
            continue
        if re.match(r"\|[\s\-:|]+\|", stripped):
            continue
        rows.append(stripped)

    if not rows:
        result.add("P0", "检查3-覆盖", "追溯表为空，无需求-用例映射")
        return

    # 检查每行是否有用例编号
    rows_without_id = []
    for row in rows:
        if not CASE_ID_PATTERN.search(row):
            rows_without_id.append(row.strip()[:60])

    if rows_without_id:
        result.add(
            "P0",
            "检查3-覆盖",
            f"追溯表 {len(rows_without_id)} 行无用例编号: "
            f"{rows_without_id[:3]}{'...' if len(rows_without_id) > 3 else ''}",
        )
    else:
        result.add(
            "P2",
            "检查3-覆盖",
            f"追溯表 {len(rows)} 行全部包含用例编号",
        )


# ============================================================
# 检查 4: 核心流程结构
# ============================================================

FLOW_HEADING_PATTERN = re.compile(r"###?\s*(?:流程\s*\d+|F-\d{2})", re.IGNORECASE)
FLOW_ID_PATTERN = re.compile(r"F-(\d{2})")


def check_core_flow_structure(content: str, result: ValidationResult):
    """检查 4: 核心流程结构 —— 流程编号连续"""
    # 找流程标题
    flow_headings = FLOW_HEADING_PATTERN.findall(content)

    if not flow_headings:
        result.add("P1", "检查4-流程", "未找到「流程N」标题，可能无核心流程测试")
        return

    # 找流程编号
    flow_ids = FLOW_ID_PATTERN.findall(content)
    if not flow_ids:
        result.add("P1", "检查4-流程", "找到流程标题但无 F-xx 编号")
        return

    # 检查连续性
    nums = sorted(int(x) for x in flow_ids)
    expected = list(range(1, nums[-1] + 1))
    missing = set(expected) - set(nums)

    if missing:
        result.add(
            "P1",
            "检查4-流程",
            f"流程编号不连续: 找到 F-{nums[0]:02d}~F-{nums[-1]:02d}，"
            f"缺失 F-{'、F-'.join(f'{m:02d}' for m in sorted(missing))}",
        )
    else:
        result.add(
            "P2",
            "检查4-流程",
            f"流程编号连续: F-{nums[0]:02d}~F-{nums[-1]:02d}，共 {len(nums)} 个流程",
        )


# ============================================================
# 检查 5: 通用覆盖矩阵
# ============================================================

MATRIX_DIMENSIONS = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]


def check_coverage_matrix(content: str, result: ValidationResult):
    """检查 5: 通用覆盖矩阵 —— A~I 触发行无空白"""
    # 找矩阵自检表
    matrix_section = re.search(
        r"##\s*通用覆盖矩阵自检\s*\n(.*?)(?=##\s|\Z)", content, re.DOTALL
    )
    if not matrix_section:
        result.add("P0", "检查5-矩阵", "未找到「通用覆盖矩阵自检」章节")
        return

    matrix_table = matrix_section.group(1)
    lines = matrix_table.split("\n")

    # 解析矩阵行
    triggered_but_empty = []
    for line in lines:
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) < 4:
            continue

        dim = cells[0]
        triggered = cells[1]  # 是否触发
        covered = cells[2]  # 已覆盖/待澄清

        # 检查每个维度行
        for d in MATRIX_DIMENSIONS:
            if dim.startswith(d) and triggered in ("是", "是", "[OK]"):
                if not covered or covered in ("", "-", "—", "待补充"):
                    triggered_but_empty.append(d)

    if triggered_but_empty:
        result.add(
            "P0",
            "检查5-矩阵",
            f"矩阵触发但未覆盖的维度: {', '.join(triggered_but_empty)}",
        )
    else:
        # 检查是否有至少一个维度被触发
        any_triggered = False
        for line in lines:
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2 and cells[1] in ("是", "是", "[OK]"):
                any_triggered = True
                break

        if any_triggered:
            result.add("P2", "检查5-矩阵", "矩阵所有触发行已覆盖")
        else:
            result.add(
                "P1",
                "检查5-矩阵",
                "矩阵自检表中无任何维度标记为「触发」",
            )


# ============================================================
# 检查 6: 交付标准
# ============================================================

REVIEW_TABLE_PATTERN = re.compile(r"##\s*用例评审表\s*\n(.*?)(?=##\s|\Z)", re.DOTALL)
PRIORITY_PATTERN = re.compile(r"P[0-3]")
CASE_ID_IN_TITLE = re.compile(r"####\s*([FLDCUXVPN T]-\d{2})")


def check_delivery_standard(content: str, result: ValidationResult):
    """检查 6: 交付标准 —— 评审表完整、编号无重复、P0 占比合理"""

    # 6a. 评审表存在
    review_section = REVIEW_TABLE_PATTERN.search(content)
    if not review_section:
        result.add("P0", "检查6-交付", "未找到「用例评审表」章节")
    else:
        review_table = review_section.group(1)
        review_rows = [
            r.strip()
            for r in review_table.split("\n")
            if r.strip().startswith("|")
            and not re.match(r"\|[\s\-:|]+\|", r.strip())
        ]
        if not review_rows:
            result.add("P0", "检查6-交付", "评审表为空")
        else:
            # 检查评审表列数（应该有 5 列：编号、名称、优先级、类型、标签）
            for row in review_rows[:3]:
                cells = [c.strip() for c in row.split("|") if c.strip()]
                if len(cells) < 5:
                    result.add(
                        "P1",
                        "检查6-交付",
                        f"评审表列数不足: 期望 5 列（编号/名称/优先级/类型/标签），"
                        f"实际 {len(cells)} 列 | 示例: {row[:60]}",
                    )
                    break

    # 6b. 评审表内编号无重复
    if review_section:
        review_ids = CASE_ID_PATTERN.findall(review_section.group(1))
        review_id_counts = Counter(review_ids)
        review_duplicates = {k: v for k, v in review_id_counts.items() if v > 1}
        if review_duplicates:
            result.add(
                "P0",
                "检查6-交付",
                f"评审表编号重复: "
                + ", ".join(f"{k} 出现 {v} 次" for k, v in review_duplicates.items()),
            )

    # 6c. P0 占比（仅统计评审表中的优先级）
    if review_section:
        priorities = PRIORITY_PATTERN.findall(review_section.group(1))
        if priorities:
            p0_count = priorities.count("P0")
            p0_ratio = p0_count / len(priorities)
            if p0_ratio > 0.20:
                result.add(
                    "P1",
                    "检查6-交付",
                    f"P0 占比过高: {p0_count}/{len(priorities)} = {p0_ratio:.0%}（建议 ≤20%）",
                )
            else:
                result.add(
                    "P2",
                    "检查6-交付",
                    f"P0 占比合理: {p0_count}/{len(priorities)} = {p0_ratio:.0%}",
                )

    # 6d. 待澄清清单
    clarification_section = re.search(
        r"##\s*待澄清清单\s*\n(.*?)(?=##\s|\Z)", content, re.DOTALL
    )
    if not clarification_section:
        result.add("P1", "检查6-交付", "未找到「待澄清清单」章节")
    else:
        clar_table = clarification_section.group(1)
        clar_rows = [
            r.strip()
            for r in clar_table.split("\n")
            if r.strip().startswith("|")
            and not re.match(r"\|[\s\-:|]+\|", r.strip())
        ]
        if clar_rows:
            result.add(
                "P2",
                "检查6-交付",
                f"待澄清清单 {len(clar_rows)} 条已汇总",
            )

    # 6e. 文档信息
    doc_info = re.search(r"##\s*文档信息\s*\n(.*?)(?=##\s|\Z)", content, re.DOTALL)
    if not doc_info:
        result.add("P1", "检查6-交付", "未找到「文档信息」章节")
    else:
        required_fields = ["依据需求", "生成版本", "测试范围"]
        info_text = doc_info.group(1)
        missing_fields = [f for f in required_fields if f not in info_text]
        if missing_fields:
            result.add(
                "P1",
                "检查6-交付",
                f"文档信息缺少字段: {', '.join(missing_fields)}",
            )


# ============================================================
# 主流程
# ============================================================

def validate_file(filepath: str) -> ValidationResult:
    """对单个测试用例文件执行全部 6 项检查"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")

    content = path.read_text(encoding="utf-8")
    result = ValidationResult()

    # 运行所有检查
    check_test_point_format(content, result)
    check_boundary_values(content, result)
    check_prd_coverage(content, result)
    check_core_flow_structure(content, result)
    check_coverage_matrix(content, result)
    check_delivery_standard(content, result)

    return result


def main():
    if len(sys.argv) < 2:
        print("用法: python step6_validator.py <测试用例.md>")
        print("  对生成的测试用例文档执行 Step 6 自检")
        sys.exit(1)

    filepath = sys.argv[1]

    print(f"=== Step 6 自检: {filepath} ===\n")

    try:
        result = validate_file(filepath)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)

    print(result.summary())
    print()

    if result.has_p0:
        print("[FAIL] 有 P0 问题，阻塞发布")
    elif result.has_p1:
        print("[WARN]  有 P1 建议，建议修复后发布")
    elif result.has_p2:
        print("[OK] 通过（有 P2 优化建议）")
    else:
        print("[OK] 全部通过，无问题")

    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
