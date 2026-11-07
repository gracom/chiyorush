#!/usr/bin/env python3
"""site/ を、GitHub Pages で配信する _site/ に書き出す。index.html には data/timetable.json を埋め込む。

ページは時刻表を読みに行かず、<script id="timetable-data"> に埋め込んだものを使う（ページからの通信をHTMLだけにする）。
リポジトリの site/index.html では、この場所は空にしてある。

使い方:
    python3 scripts/build_site.py          # _site/ に書き出す
    python3 scripts/build_site.py OUTDIR   # 書き出し先を指定する
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SITE_DIR = REPO / "site"
DATA_PATH = REPO / "data" / "timetable.json"
EMBED_RE = re.compile(r'(<script type="application/json" id="timetable-data">)(.*?)(</script>)', re.S)


def embed(page: str, data: str) -> str:
    if not EMBED_RE.search(page):
        raise SystemExit("site/index.html に timetable-data が見つからない")
    return EMBED_RE.sub(lambda m: m.group(1) + data + m.group(3), page, count=1)


def main() -> int:
    out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO / "_site"
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE_DIR, out)
    data = DATA_PATH.read_text(encoding="utf-8").rstrip("\n")
    page = (SITE_DIR / "index.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(embed(page, data), encoding="utf-8", newline="\n")
    print(f"wrote {out}: {', '.join(sorted(p.name for p in out.iterdir()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
