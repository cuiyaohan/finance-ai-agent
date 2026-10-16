#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""高危词扫描器（替代 grep -F -f）。

为什么不用 grep：
  BSD grep（macOS）在多模式文件（-f）下对多字节 UTF-8 存在边界效应，
  会把 `git clone ...` 这类正常文本误判为命中 `vx` 等词——已实测复现。
  而 Python 的 str.__contains__ 是逐码点精确匹配，无此问题。

用法：
    python3 scan_high_risk.py --words _shared/high_risk_words.txt --scan docs README.md [...]
    # 退出码 0 = 零命中；1 = 有命中
"""
import argparse
import os
import sys

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", ".tools", ".idea"}
TEXT_EXT = {
    ".md", ".txt", ".html", ".htm", ".py", ".java", ".yml", ".yaml",
    ".json", ".jsonl", ".csv", ".sh", ".xml", ".example", ".gitignore",
}


def load_words(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if w and not w.startswith("#"):
                out.append(w)
    return out


def iter_files(targets):
    for t in targets:
        if os.path.isfile(t):
            yield t
        elif os.path.isdir(t):
            for root, dirs, files in os.walk(t):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for fn in files:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in TEXT_EXT or fn in ("Dockerfile", ".gitignore", ".env.example"):
                        yield os.path.join(root, fn)


# 引用外部原文的标记行（新闻标题/摘要等），其内容由第三方信源提供，
# 不属于本项目对外文案，命中高危词属客观事实陈述而非违规宣传。
QUOTE_MARKERS = ("原文：", "原文:", "[引用]", "来源：外部")


def is_quoted(text):
    return any(m in text for m in QUOTE_MARKERS)


def main():
    ap = argparse.ArgumentParser(description="高危词精确扫描（Python 实现）")
    ap.add_argument("--words", required=True)
    ap.add_argument("--scan", nargs="+", required=True)
    ap.add_argument(
        "--include-quotes",
        action="store_true",
        help="连同外部引用原文一起扫描（默认跳过客观事实陈述）",
    )
    args = ap.parse_args()

    words = load_words(args.words)
    hits = []
    skipped = []
    scanned = 0

    for path in iter_files(args.scan):
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.read().split("\n")
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        for i, line in enumerate(lines, 1):
            for w in words:
                if w in line:
                    item = (path, i, w, line.strip()[:90])
                    if not args.include_quotes and is_quoted(line):
                        skipped.append(item)
                    else:
                        hits.append(item)

    if skipped:
        print(f"（已跳过 {len(skipped)} 处外部引用原文中的客观表述）")
        for path, ln, w, text in skipped[:3]:
            print(f"  引用 {path}:{ln}  [{w}]")

    if hits:
        for path, ln, w, text in hits:
            print(f"命中 {path}:{ln}  [{w}]  {text}")
        print(f"\n共 {len(hits)} 处命中（已扫 {scanned} 个文件）")
        sys.exit(1)

    print(f"零命中（已扫 {scanned} 个文件，{len(words)} 个词）")
    sys.exit(0)


if __name__ == "__main__":
    main()