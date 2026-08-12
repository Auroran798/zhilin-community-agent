from __future__ import annotations

from pathlib import Path


def write_stage6_reports(profiles: list[dict], manifests: list[dict], output: Path) -> None:
    lines = ["# 阶段 6 真实公开数据质量与隐私报告", "", "本报告中的记录来自美国纽约市 HPD 官方公开数据。它们是历史公共监管记录，不能被描述为中国物业公司生产数据，也不代表任何地址的当前状态。", "", "## 数据规模与质量", "", "| 数据集 | 原始记录 | 字段数 | 重复源 ID | PII 模式命中 |", "| --- | ---: | ---: | ---: | ---: |"]
    for profile in profiles:
        lines.append(f"| {Path(profile['file']).name} | {profile['row_count']} | {profile['column_count']} | {profile['duplicate_id_count']} | {profile['pii_pattern_hits']} |")
    lines.extend(["", "## 隐私边界", "", "- 原始层仅使用最小化官方 API 字段；不请求街道门牌、单元、经纬度、姓名、电话、邮箱或账户信息。", "- 原始层不被 Agent、MCP 或 Web 接口读取。", "- 业务数据库只保存 `sanitized_text`、粗粒度位置、来源字段名和不可逆原始行哈希；原始文本/完整载荷不导入业务表，任何 LLM 输入必须使用 `sanitized_text`。", "- 不创建真实居民、房屋绑定、账单、付款、维修人员、派单时间线或住户评价。", "", "## 许可证与使用限制", "", "- NYC Open Data 的公开数据可获取和使用，但仍受 NYC.gov Terms/Privacy Policy 和机构附加条款约束；数据按信息用途提供，不保证完整性、准确性或适用性。", "- 应注明 NYC HPD 来源、版本/获取时间和修改；不得将历史违规作为当前房屋状态、法律意见或中国物业法规依据。", "", "## 清单", ""])
    for manifest in manifests:
        lines.append(f"- `{manifest['dataset_name']}`: {manifest['row_count']} rows, SHA-256 `{manifest['sha256']}`")
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text("\n".join(lines) + "\n", encoding="utf-8")
