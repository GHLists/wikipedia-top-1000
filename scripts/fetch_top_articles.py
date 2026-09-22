#!/usr/bin/env python3
"""Fetch the top Wikipedia articles by pageviews for a single UTC day."""

import argparse
import csv
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
    "{project}/all-access/{year:04d}/{month:02d}/{day:02d}"
)
DEFAULT_USER_AGENT = "wikipedia-top-1000/1.0 (https://github.com/wikipedia-top-1000)"


class NotFound(Exception):
    pass


def fetch_day(project, day, user_agent, retries=3, backoff=5.0):
    url = API_URL.format(
        project=project, year=day.year, month=day.month, day=day.day
    )
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise NotFound(url) from error
            last_error = error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
        if attempt < retries:
            print(f"attempt {attempt} failed ({last_error}), retrying", file=sys.stderr)
            time.sleep(backoff * attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def resolve_day(project, requested, user_agent, allow_fallback, retries):
    day = requested
    for _ in range(7):
        try:
            return day, fetch_day(project, day, user_agent, retries=retries)
        except NotFound:
            if not allow_fallback:
                raise
            print(f"no data published for {day}, trying previous day", file=sys.stderr)
            day -= dt.timedelta(days=1)
    raise RuntimeError(f"no pageview data found between {requested} and {day}")


def write_csv(path, day, project, articles, limit):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "article", "views", "date", "project"])
        for article in articles[:limit]:
            writer.writerow(
                [
                    article.get("rank"),
                    article.get("article"),
                    article.get("views"),
                    day.isoformat(),
                    project,
                ]
            )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        help="UTC day to fetch as YYYY-MM-DD (default: yesterday)",
    )
    parser.add_argument("--project", default="en.wikipedia")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="fail instead of falling back to earlier days when data is missing",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    requested = (
        dt.date.fromisoformat(args.date)
        if args.date
        else dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    )

    try:
        day, payload = resolve_day(
            args.project,
            requested,
            args.user_agent,
            allow_fallback=not args.no_fallback,
            retries=args.retries,
        )
    except NotFound as error:
        print(f"no pageview data available: {error}", file=sys.stderr)
        return 1

    items = payload.get("items") or []
    if not items:
        print(f"unexpected API response for {day}: missing items", file=sys.stderr)
        return 1

    articles = items[0].get("articles") or []
    output = Path(args.output_dir) / f"top-{args.limit}-{day.isoformat()}.csv"
    write_csv(output, day, args.project, articles, args.limit)
    print(f"wrote {min(len(articles), args.limit)} articles for {day} to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
