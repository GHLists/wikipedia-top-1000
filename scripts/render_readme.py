#!/usr/bin/env python3
"""Render a README with a language map and the latest English top-articles table."""

import argparse
import csv
import sys
import urllib.parse
from pathlib import Path

from fetch_top_articles import DEFAULT_PROJECTS

LANGUAGE_NAMES = {
    "en": "English",
    "ja": "Japanese",
    "zh": "Chinese",
    "fr": "French",
    "de": "German",
    "ru": "Russian",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "pl": "Polish",
    "ar": "Arabic",
    "fa": "Persian",
    "tr": "Turkish",
    "he": "Hebrew",
    "sv": "Swedish",
    "nl": "Dutch",
    "ko": "Korean",
    "id": "Indonesian",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
}

INTRO = """\
# Wikipedia Top 1000

Daily top 1000 articles by pageviews for the most-read Wikipedia language
editions, taken from the [Wikimedia Pageviews API](https://wikimedia.org/api/rest_v1/)
for the previous UTC day. A GitHub Actions workflow fetches the data every day
and commits one CSV per language to [`data/`](data/), e.g.
[`data/en/top-1000-<date>.csv`](data/en/).

Pick a language below to open its latest CSV, or read the English ranking
further down.
"""

EN_SECTION = """\
## {name} ({code}) \u2014 {day}

[Full CSV]({csv_path})

| Rank | Article | Views |
| ---: | :------ | ----: |
{rows}
"""


def collect(data_dir):
    by_code = {}
    for path in Path(data_dir).glob("*/top-1000-*.csv"):
        code = path.parent.name
        day = path.stem.removeprefix("top-1000-")
        by_code.setdefault(code, {})[day] = path
    return by_code


def ordered_codes(by_code):
    known = [code for code in DEFAULT_PROJECTS if code in by_code]
    extra = sorted(code for code in by_code if code not in DEFAULT_PROJECTS)
    return known + extra


def load_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            {
                "rank": row["rank"],
                "article": row["article"],
                "views": int(row["views"]),
            }
            for row in reader
        ]


def article_link(code, article):
    url = f"https://{code}.wikipedia.org/wiki/" + urllib.parse.quote(article)
    label = article.replace("_", " ").replace("|", "\\|")
    return f"[{label}]({url})"


def render_rows(code, rows):
    return "\n".join(
        f"| {row['rank']} | {article_link(code, row['article'])} | {row['views']:,} |"
        for row in rows
    )


def render_map(by_code, codes):
    lines = ["| Language | Code | Latest |", "| :------- | :--- | :----- |"]
    for code in codes:
        day = max(by_code[code])
        path = by_code[code][day].as_posix()
        name = LANGUAGE_NAMES.get(code, code)
        lines.append(f"| {name} | `{code}` | [{day}]({path}) |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default="README.md")
    args = parser.parse_args(argv)

    by_code = collect(args.data_dir)
    if not by_code:
        print(f"no top-1000 CSV found in {args.data_dir}", file=sys.stderr)
        return 1

    codes = ordered_codes(by_code)
    content = INTRO + "\n## Languages\n\n" + render_map(by_code, codes) + "\n\n"

    if "en" in by_code:
        day = max(by_code["en"])
        path = by_code["en"][day]
        content += EN_SECTION.format(
            name=LANGUAGE_NAMES["en"],
            code="en",
            day=day,
            csv_path=path.as_posix(),
            rows=render_rows("en", load_rows(path)),
        )
    else:
        print("no English CSV found; map rendered without the ranking", file=sys.stderr)

    Path(args.output).write_text(content, encoding="utf-8")
    print(f"wrote language map ({len(codes)} languages) to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
