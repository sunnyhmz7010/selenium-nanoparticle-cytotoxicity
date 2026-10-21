"""将中文论文打包到本次空发布目录，递归展开正文和表格。"""

import argparse
import re
import shutil
from pathlib import Path


INPUT = re.compile(r"\\input\{([^}]+)\}")
ASSET = re.compile(r"\\(?:addbibresource|includegraphics)(?:\[[^\]]*\])?\{([^}]+)\}")


def package(source: Path, destination: Path, timestamp: str) -> Path:
    if not re.fullmatch(r"\d{8}_\d{6}", timestamp):
        raise ValueError("时间戳必须采用 YYYYMMDD_HHMMSS 格式")
    source = source.resolve()
    root = source.parent

    def expand(path: Path, parents: tuple[Path, ...] = ()) -> str:
        path = path.resolve()
        path.relative_to(root)
        if path in parents:
            raise ValueError(f"循环 input 引用：{path}")
        text = path.read_text(encoding="utf-8")

        def replace(match: re.Match) -> str:
            # LaTeX 当前入口的所有 input 均相对于编译工作目录 paper/v2。
            included = root / match.group(1)
            if not included.suffix:
                included = included.with_suffix(".tex")
            return expand(included, parents + (path,))

        return INPUT.sub(replace, text)

    merged = expand(source)
    title_match = re.search(r"\\title\{([^}]+)\}", merged)
    if title_match is None:
        raise ValueError("未找到论文标题")
    title = re.sub(r"\\\\(?:\[[^\]]*\])?", " ", title_match.group(1))
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " - ", title)
    title = re.sub(r"\s+", " ", title).strip(" .")
    pdf = source.with_suffix(".pdf")
    if not pdf.is_file():
        raise FileNotFoundError(f"缺少编译产物：{pdf}")

    # 先核验依赖完整性，再写入；保持图的相对路径，使 main.tex 可独立编译。
    assets = []
    for name in sorted(set(ASSET.findall(merged))):
        asset = (root / name).resolve()
        relative = asset.relative_to(root)
        if not asset.is_file():
            raise FileNotFoundError(f"缺少稿源依赖：{asset}")
        assets.append((asset, relative))

    destination.mkdir(parents=True, exist_ok=True)
    output_pdf = destination / f"{timestamp}_{title}.pdf"
    if output_pdf.exists():
        raise FileExistsError(f"同一时间戳的 PDF 已存在：{output_pdf}")
    shutil.copy2(pdf, output_pdf)
    (destination / "main.tex").write_text(merged, encoding="utf-8", newline="\n")
    for asset, relative in assets:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, target)
    return output_pdf


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("timestamp")
    args = parser.parse_args()
    print(package(args.source, args.destination, args.timestamp))
