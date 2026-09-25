"""Task 3 - Normalize landing legal/news datasets into Markdown."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pdfplumber


ROOT = Path(__file__).parent.parent
LANDING_DIR = ROOT / "data" / "landing"
OUTPUT_DIR = ROOT / "data" / "standardized"

HEADER_CODE = re.compile(r"^\d{9}$")
FOOTER = re.compile(r"^\d+\s+Bao Viet Life$")
CHAPTER = re.compile(
    r"^(CH\u01af\u01a0NG\s+[IVXLCDM]+|PH\u1ee4 L\u1ee4C\s+\d+)\b",
    re.IGNORECASE,
)
ARTICLE = re.compile(r"^\u0110i\u1ec1u\s+\d+\s*:", re.IGNORECASE)
NUMBERED = re.compile(r"^(\d+(?:\.\d+)+\.?)(?:\s+|$)")
ALPHA_ITEM = re.compile(r"^[a-z\u0111]\)\s+", re.IGNORECASE)
BULLET = re.compile(r"^([-+])\s+")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value.replace("\u00a0", " "))
    return re.sub(r"[ \t]+", " ", value).strip()


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def legal_metadata(path: Path) -> dict[str, str]:
    upper = path.stem.upper()
    if "CAO CAP" in upper:
        plan, label = "cao_cap", "Cao c\u1ea5p"
    elif "NANG CAO" in upper:
        plan, label = "nang_cao", "N\u00e2ng cao"
    elif "CO BAN" in upper:
        plan, label = "co_ban", "C\u01a1 b\u1ea3n"
    else:
        plan, label = "khong_xac_dinh", "Kh\u00f4ng x\u00e1c \u0111\u1ecbnh"
    return {
        "title": f"An Khang H\u1ea1nh Ph\u00fac 2024 - Ch\u01b0\u01a1ng tr\u00ecnh {label}",
        "source": path.name,
        "doc_type": "legal",
        "product": "An Khang H\u1ea1nh Ph\u00fac 2024",
        "plan": plan,
    }


def visible_page(page: Any) -> Any:
    """Discard hidden text outside the physical page."""
    return page.crop((0, 0, page.width, page.height), strict=False)


def cell_text(
    page: Any,
    cell: tuple[float, float, float, float],
    *,
    last_column: bool,
) -> str:
    x0, top, x1, bottom = cell
    if last_column:
        x1 = min(page.width, x1 + min(80, page.width * 0.15))
    text = page.crop((x0, top, x1, bottom), strict=False).extract_text(
        x_tolerance=2,
        y_tolerance=3,
    )
    text = re.sub(r"\s+", " ", text or "")
    return normalize(text).replace("|", r"\|")


def table_to_markdown(page: Any, table: Any) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        values = [
            (
                cell_text(page, cell, last_column=index == len(row.cells) - 1)
                if cell is not None
                else ""
            )
            for index, cell in enumerate(row.cells)
        ]
        if any(values):
            rows.append(values)

    if not rows:
        return ""

    column_count = max(map(len, rows))
    rows = [row + [""] * (column_count - len(row)) for row in rows]
    separator = ["---"] * column_count
    if column_count > 1:
        separator[-1] = "---:"

    output = [
        "| " + " | ".join(rows[0]) + " |",
        "|" + "|".join(separator) + "|",
    ]
    output.extend("| " + " | ".join(row) + " |" for row in rows[1:])
    return "\n".join(output)


def is_new_block(line: str) -> bool:
    return bool(
        CHAPTER.match(line)
        or ARTICLE.match(line)
        or NUMBERED.match(line)
        or ALPHA_ITEM.match(line)
        or BULLET.match(line)
    )


def format_block(lines: list[str]) -> str:
    first = lines[0]
    text = re.sub(r"\s+", " ", " ".join(lines)).strip()

    if CHAPTER.match(first):
        return f"# {text}"
    if ARTICLE.match(first):
        return f"## {text}"

    section = NUMBERED.match(first)
    if section:
        level = min(4, max(2, section.group(1).count(".") + 1))
        return f'{"#" * level} {text}'

    bullet = BULLET.match(first)
    if bullet:
        content = BULLET.sub("", text, count=1)
        indent = "  " if bullet.group(1) == "+" else ""
        return f"{indent}- {content}"

    return text


def text_to_markdown(text: str) -> str:
    lines = [normalize(line) for line in text.splitlines()]
    lines = [
        line
        for line in lines
        if line and not HEADER_CODE.fullmatch(line) and not FOOTER.fullmatch(line)
    ]

    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if is_new_block(line):
            if current:
                blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)

    return "\n\n".join(format_block(block) for block in blocks if block)


def page_to_markdown(page: Any, page_number: int) -> str:
    page = visible_page(page)
    tables = sorted(page.find_tables(), key=lambda item: item.bbox[1])
    sections = [f"<!-- page: {page_number} -->"]
    cursor = 0.0

    for table in tables:
        _, top, _, bottom = table.bbox
        if top > cursor:
            region = page.crop((0, cursor, page.width, top), strict=False)
            text = text_to_markdown(
                region.extract_text(x_tolerance=2, y_tolerance=3) or ""
            )
            if text:
                sections.append(text)

        converted_table = table_to_markdown(page, table)
        if converted_table:
            sections.append(converted_table)
        cursor = max(cursor, bottom)

    if cursor < page.height:
        region = page.crop((0, cursor, page.width, page.height), strict=False)
        text = text_to_markdown(
            region.extract_text(x_tolerance=2, y_tolerance=3) or ""
        )
        if text:
            sections.append(text)

    return "\n\n".join(sections)


def legal_frontmatter(metadata: dict[str, str], page_count: int) -> str:
    values = {**metadata, "page_count": str(page_count)}
    lines = ["---"]
    lines.extend(
        f"{key}: {yaml_string(value)}"
        for key, value in values.items()
    )
    lines.append("---")
    return "\n".join(lines)


def legal_output_name(path: Path, plan: str) -> str:
    if plan != "khong_xac_dinh":
        return f"an-khang-hanh-phuc-{plan.replace('_', '-')}.md"
    name = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    return f"{name}.md"


def convert_pdf(path: Path, output_dir: Path) -> Path:
    metadata = legal_metadata(path)
    output_path = output_dir / legal_output_name(path, metadata["plan"])

    with pdfplumber.open(path) as pdf:
        pages = [
            page_to_markdown(page, number)
            for number, page in enumerate(pdf.pages, start=1)
        ]
        body = "\n\n".join(page for page in pages if page.strip())
        content = f"{legal_frontmatter(metadata, len(pdf.pages))}\n\n{body}\n"

    if len(body.strip()) < 200:
        raise ValueError(f"PDF did not produce enough text: {path.name}")
    output_path.write_text(content, encoding="utf-8", newline="\n")
    return output_path


def convert_docx(path: Path, output_dir: Path) -> Path:
    from markitdown import MarkItDown

    result = MarkItDown().convert(str(path))
    body = str(result.text_content or "").strip()
    if len(body) < 200:
        raise ValueError(f"DOCX did not produce enough text: {path.name}")

    metadata = legal_metadata(path)
    output_path = output_dir / legal_output_name(path, metadata["plan"])
    output_path.write_text(
        f"{legal_frontmatter(metadata, 0)}\n\n{body}\n",
        encoding="utf-8",
        newline="\n",
    )
    return output_path


def convert_legal_docs() -> list[Path]:
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    for path in sorted(legal_dir.iterdir()):
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            outputs.append(convert_pdf(path, output_dir))
        elif suffix in {".doc", ".docx"}:
            outputs.append(convert_docx(path, output_dir))
    return outputs


def convert_news_articles() -> list[Path]:
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    required = ("url", "title", "date_crawled", "content_markdown")

    for path in sorted(news_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = [key for key in required if not str(data.get(key, "")).strip()]
        if missing:
            raise ValueError(f"{path.name} missing: {', '.join(missing)}")

        header = (
            "---\n"
            f"title: {yaml_string(str(data['title']))}\n"
            f"source: {yaml_string(path.name)}\n"
            'doc_type: "news"\n'
            f"url: {yaml_string(str(data['url']))}\n"
            f"date_crawled: {yaml_string(str(data['date_crawled']))}\n"
            "---\n\n"
        )
        output_path = output_dir / f"{path.stem}.md"
        output_path.write_text(
            header + str(data["content_markdown"]).strip() + "\n",
            encoding="utf-8",
            newline="\n",
        )
        outputs.append(output_path)
    return outputs


def convert_all() -> tuple[list[Path], list[Path]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    legal_outputs = convert_legal_docs()
    news_outputs = convert_news_articles()
    print(
        f"Saved {len(legal_outputs)} legal and "
        f"{len(news_outputs)} news Markdown files"
    )
    return legal_outputs, news_outputs


if __name__ == "__main__":
    convert_all()
