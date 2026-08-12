"""Build the sanitized, self-contained final submission directory.

This is an artifact builder: it copies audited source inputs, creates readable
Chinese PDFs from the maintained Markdown reports, and stages machine-readable
evidence. The Docker image tar and checksums are added after the image build.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = Path.home() / "Desktop" / "智邻管家_北京物业智能体_最终提交版"

SOURCE_DIRECTORIES = (
    ".github",
    "agent",
    "alembic",
    "api",
    "data",
    "data_pipeline",
    "docs",
    "domain",
    "evals",
    "harness",
    "mcp_server",
    "rag",
    "requirements",
    "scripts",
    "skills",
    "tests",
    "web",
)
SOURCE_FILES = (
    ".dockerignore",
    ".env.example",
    ".gitignore",
    "alembic.ini",
    "CHANGELOG.md",
    "docker-compose.yml",
    "docker-compose.public-real.yml",
    "Dockerfile",
    "Dockerfile.offline",
    "Makefile",
    "pyproject.toml",
    "README.md",
    "RELEASE_NOTES.md",
    "THIRD_PARTY_NOTICES.md",
    "VERSION",
    "智邻管家物业社区管理智能体项目实施提纲（完善版）.md",
)

PDF_INPUTS = {
    "项目完整解决方案.pdf": ROOT / "docs/101_beijing_complete_solution.md",
    "最终验收报告.pdf": ROOT / "docs/100_beijing_final_acceptance.md",
    "北京官方知识目录.pdf": ROOT / "docs/95_beijing_official_knowledge_catalog.md",
    "数据卡.pdf": ROOT / "docs/96_beijing_data_card.md",
    "RAG评测报告.pdf": ROOT / "docs/97_beijing_rag_evaluation_report.md",
    "Agent评测报告.pdf": ROOT / "docs/98_beijing_agent_evaluation_report.md",
    "安全报告.pdf": ROOT / "docs/99_beijing_security_report.md",
    "智能体完整功能验证文档.pdf": ROOT / "submission/智能体完整功能验证文档.md",
}

EVIDENCE = {
    "final_acceptance.json": ROOT / "artifacts/acceptance/final_acceptance.json",
    "latest_results.json": ROOT / "evals/rag/latest_results.json",
    "latest_security_results.json": ROOT / "evals/beijing/latest_security_results.json",
    "stage5_security_summary.json": ROOT / "artifacts/security/stage5_security_summary.json",
}

SKIP_PARTS = {
    ".git",
    ".venv",
    ".venv313",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "htmlcov",
    "tmp",
    "tmp_pdf_review",
    "zhilin_community_agent.egg-info",
}


def ignored(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    parts = relative.parts
    if any(part in SKIP_PARTS for part in parts):
        return True
    lowered = {part.lower() for part in parts}
    if path.suffix.lower() in {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}:
        return True
    if "data" in lowered and "knowledge" in lowered and ({"chroma", "chroma_beijing_v1", "files"} & lowered):
        return True
    if len(parts) >= 3 and parts[0] == "data" and parts[1] == "public_real" and parts[2] in {"raw", "processed", "normalized"}:
        return True
    if parts and parts[0] == "artifacts":
        return True
    return False


def copy_tree(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        if ignored(path):
            continue
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def register_fonts() -> tuple[str, str]:
    candidates = [
        (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/msyhbd.ttc")),
        (Path("C:/Windows/Fonts/simhei.ttf"), Path("C:/Windows/Fonts/simhei.ttf")),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("ZhilinCJK", str(regular), subfontIndex=0))
            pdfmetrics.registerFont(TTFont("ZhilinCJKBold", str(bold), subfontIndex=0))
            return "ZhilinCJK", "ZhilinCJKBold"
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light", "STSong-Light"


def plain_inline(value: str) -> str:
    value = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1（\2）", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    return html.escape(value, quote=False).replace("  ", " &nbsp;")


def make_styles(regular: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ZTitle", parent=base["Title"], fontName=bold, fontSize=23,
            leading=32, textColor=colors.HexColor("#143E63"), alignment=TA_CENTER,
            spaceAfter=14 * mm, wordWrap="CJK",
        ),
        "h1": ParagraphStyle(
            "ZH1", parent=base["Heading1"], fontName=bold, fontSize=16,
            leading=23, textColor=colors.HexColor("#143E63"), spaceBefore=7 * mm,
            spaceAfter=3 * mm, wordWrap="CJK", keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "ZH2", parent=base["Heading2"], fontName=bold, fontSize=13,
            leading=19, textColor=colors.HexColor("#1E5D87"), spaceBefore=5 * mm,
            spaceAfter=2 * mm, wordWrap="CJK", keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "ZH3", parent=base["Heading3"], fontName=bold, fontSize=11.2,
            leading=17, textColor=colors.HexColor("#24769C"), spaceBefore=4 * mm,
            spaceAfter=1.5 * mm, wordWrap="CJK", keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "ZBody", parent=base["BodyText"], fontName=regular, fontSize=9.5,
            leading=15.5, textColor=colors.HexColor("#202B33"), alignment=TA_LEFT,
            spaceAfter=2.2 * mm, wordWrap="CJK", allowWidows=0, allowOrphans=0,
        ),
        "bullet": ParagraphStyle(
            "ZBullet", parent=base["BodyText"], fontName=regular, fontSize=9.4,
            leading=15.2, leftIndent=6 * mm, firstLineIndent=-4 * mm,
            textColor=colors.HexColor("#202B33"), spaceAfter=1.1 * mm, wordWrap="CJK",
        ),
        "quote": ParagraphStyle(
            "ZQuote", parent=base["BodyText"], fontName=regular, fontSize=9.3,
            leading=15, leftIndent=7 * mm, rightIndent=4 * mm,
            borderColor=colors.HexColor("#7FAFC9"), borderWidth=0,
            borderPadding=(2 * mm, 3 * mm, 2 * mm, 3 * mm),
            backColor=colors.HexColor("#F1F7FA"), textColor=colors.HexColor("#254557"),
            spaceAfter=2.5 * mm, wordWrap="CJK",
        ),
        "code": ParagraphStyle(
            "ZCode", parent=base["Code"], fontName=regular, fontSize=8.2,
            leading=12.5, leftIndent=3 * mm, rightIndent=3 * mm,
            borderPadding=2.5 * mm, backColor=colors.HexColor("#F4F5F6"),
            textColor=colors.HexColor("#25313A"), spaceBefore=1 * mm,
            spaceAfter=3 * mm, wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "ZTable", parent=base["BodyText"], fontName=regular, fontSize=7.7,
            leading=11.2, wordWrap="CJK", textColor=colors.HexColor("#1D2931"),
        ),
        "table_head": ParagraphStyle(
            "ZTableHead", parent=base["BodyText"], fontName=bold, fontSize=7.8,
            leading=11.3, wordWrap="CJK", textColor=colors.white,
        ),
    }


def split_table(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    cells = split_table(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def table_flowable(rows: list[list[str]], styles: dict[str, ParagraphStyle], regular: str, bold: str) -> Table:
    columns = max(len(row) for row in rows)
    normalized = [row + [""] * (columns - len(row)) for row in rows]
    wrapped = []
    for row_index, row in enumerate(normalized):
        style = styles["table_head"] if row_index == 0 else styles["table"]
        wrapped.append([Paragraph(plain_inline(cell), style) for cell in row])
    usable = A4[0] - 36 * mm
    weights = []
    for index in range(columns):
        longest = max((len(row[index]) for row in normalized), default=1)
        weights.append(min(max(longest, 8), 32))
    total = sum(weights) or columns
    widths = [usable * weight / total for weight in weights]
    table = Table(wrapped, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E5D87")),
        ("FONTNAME", (0, 0), (-1, 0), bold),
        ("FONTNAME", (0, 1), (-1, -1), regular),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B9C8D0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F9FA")]),
    ]))
    return table


def markdown_story(text: str, styles: dict[str, ParagraphStyle], regular: str, bold: str):
    lines = text.replace("\r\n", "\n").split("\n")
    story = []
    index = 0
    first_heading = True
    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("```"):
            index += 1
            code = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index].rstrip())
                index += 1
            index += 1
            content = "<br/>".join(html.escape(line, quote=False).replace(" ", "&nbsp;") or "&nbsp;" for line in code)
            story.append(Paragraph(content, styles["code"]))
            continue
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()
            if level == 1 and first_heading:
                story.append(Spacer(1, 8 * mm))
                story.append(Paragraph(plain_inline(title), styles["title"]))
                story.append(Table([[""]], colWidths=[48 * mm], rowHeights=[0.8 * mm], style=[("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#45A4B8"))], hAlign="CENTER"))
                story.append(Spacer(1, 8 * mm))
                first_heading = False
            else:
                key = "h1" if level == 1 else "h2" if level == 2 else "h3"
                story.append(Paragraph(plain_inline(title), styles[key]))
            index += 1
            continue
        if "|" in stripped and index + 1 < len(lines) and is_table_separator(lines[index + 1].strip()):
            rows = [split_table(stripped)]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(split_table(lines[index]))
                index += 1
            story.append(Spacer(1, 1 * mm))
            story.append(table_flowable(rows, styles, regular, bold))
            story.append(Spacer(1, 3 * mm))
            continue
        bullet = re.match(r"^[-*+]\s+(.+)$", stripped)
        numbered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if bullet:
            story.append(Paragraph("• &nbsp;" + plain_inline(bullet.group(1)), styles["bullet"]))
            index += 1
            continue
        if numbered:
            story.append(Paragraph(f"{numbered.group(1)}. &nbsp;" + plain_inline(numbered.group(2)), styles["bullet"]))
            index += 1
            continue
        if stripped.startswith(">"):
            quote_lines = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(lines[index].strip().lstrip(">").strip())
                index += 1
            story.append(Paragraph("<br/>".join(plain_inline(line) for line in quote_lines), styles["quote"]))
            continue
        if re.fullmatch(r"[-_*]{3,}", stripped):
            story.append(Spacer(1, 2 * mm))
            index += 1
            continue

        paragraph = [stripped]
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate or candidate.startswith(("#", "```", ">")):
                break
            if re.match(r"^[-*+]\s+", candidate) or re.match(r"^\d+\.\s+", candidate):
                break
            if "|" in candidate and index + 1 < len(lines) and is_table_separator(lines[index + 1].strip()):
                break
            paragraph.append(candidate)
            index += 1
        story.append(Paragraph(plain_inline(" ".join(paragraph)), styles["body"]))
    return story


def build_pdf(source: Path, target: Path, regular: str, bold: str) -> None:
    styles = make_styles(regular, bold)
    document = SimpleDocTemplate(
        str(target), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=19 * mm, bottomMargin=17 * mm,
        title=source.stem, author="智邻管家项目组",
        subject="智邻管家北京物业智能体最终提交版",
    )

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D7E1E6"))
        canvas.setLineWidth(0.4)
        canvas.line(18 * mm, 13.5 * mm, A4[0] - 18 * mm, 13.5 * mm)
        canvas.setFont(regular, 7.5)
        canvas.setFillColor(colors.HexColor("#65747D"))
        canvas.drawString(18 * mm, 8.8 * mm, "智邻管家｜北京物业智能体最终提交版")
        canvas.drawRightString(A4[0] - 18 * mm, 8.8 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    story = markdown_story(source.read_text(encoding="utf-8"), styles, regular, bold)
    document.build(story, onFirstPage=decorate, onLaterPages=decorate)


def ensure_empty_target(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    existing = list(target.iterdir())
    if existing:
        raise SystemExit(f"Target must be empty before staging: {target}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    target = args.target.resolve()
    ensure_empty_target(target)

    source_target = target / "source"
    source_target.mkdir()
    for directory in SOURCE_DIRECTORIES:
        copy_tree(ROOT / directory, source_target / directory)
    for file_name in SOURCE_FILES:
        source = ROOT / file_name
        if not source.exists():
            raise SystemExit(f"Missing source input: {source}")
        shutil.copy2(source, source_target / file_name)

    docker_target = target / "docker"
    docker_target.mkdir()
    shutil.copy2(ROOT / "submission/docker-compose.submit.yml", docker_target / "docker-compose.submit.yml")
    for file_name in (
        "START_HERE.md",
        "一键启动-Windows.ps1",
        "一键启动-Linux.sh",
        "停止服务-Windows.ps1",
        "停止服务-Linux.sh",
        "运行检查.ps1",
    ):
        source = ROOT / "submission" / file_name
        destination = target / file_name
        if source.suffix.lower() == ".ps1":
            # Windows PowerShell 5.1 otherwise decodes non-BOM UTF-8 with the
            # active legacy code page and can turn Chinese string literals
            # into parser errors.
            destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8-sig")
        else:
            shutil.copy2(source, destination)

    documents = target / "documents"
    documents.mkdir()
    verification_source = ROOT / "submission/智能体完整功能验证文档.md"
    shutil.copy2(verification_source, documents / "智能体完整功能验证文档.md")
    regular, bold = register_fonts()
    for name, source in PDF_INPUTS.items():
        if not source.exists():
            raise SystemExit(f"Missing PDF input: {source}")
        build_pdf(source, documents / name, regular, bold)

    evidence = target / "evidence"
    evidence.mkdir()
    for name, source in EVIDENCE.items():
        if not source.exists():
            raise SystemExit(f"Missing evidence input: {source}")
        shutil.copy2(source, evidence / name)

    print(target)


if __name__ == "__main__":
    main()
