from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from dataclasses import dataclass
from html import unescape


DEFAULT_SOURCE_URL = "https://lotto.hawo.tw/lotto/recent-50"

SAMPLE_HTML = """
<div class="result-item">
  <div class="result-item-simple-area-container">
    <div class="result-item-simple-area">
      <div class="result-item-simple-area-period">
        <div class="period-title">第115000049期</div>
        <div class="period-date">開獎日期 115/05/01</div>
      </div>
      <div class="result-item-simple-area-order-container">
        <div class="balls">
          <span class="ball ball-orange">07</span>
          <span class="ball ball-orange">22</span>
          <span class="ball ball-orange">27</span>
          <span class="ball ball-orange">35</span>
          <span class="ball ball-orange">43</span>
          <span class="ball ball-orange">48</span>
        </div>
        <span class="ball ball-red">45</span>
      </div>
    </div>
  </div>
</div>
"""


@dataclass(frozen=True)
class LottoResult:
    period: str
    date: str
    numbers: list[str]
    special: str


def clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_number(value: str) -> str:
    return f"{int(value):02d}"


def find_text(pattern: str, html: str, default: str = "") -> str:
    match = re.search(pattern, html, flags=re.S | re.I)
    return clean_text(match.group(1)) if match else default


def extract_class_text(html: str, tag: str, class_name: str) -> list[str]:
    pattern = (
        rf"<{tag}\b(?=[^>]*\bclass=[\"'][^\"']*\b{re.escape(class_name)}\b)"
        rf"[^>]*>(.*?)</{tag}>"
    )
    return [clean_text(value) for value in re.findall(pattern, html, flags=re.S | re.I)]


def parse_sample_html(html: str = SAMPLE_HTML) -> LottoResult:
    period = find_text(r'<div\s+class=["\']period-title["\'][^>]*>.*?(\d{9}).*?</div>', html)
    date = find_text(r'<div\s+class=["\']period-date["\'][^>]*>.*?(\d{3}/\d{2}/\d{2}).*?</div>', html)
    numbers = [normalize_number(value) for value in extract_class_text(html, "span", "ball-orange")]
    red_balls = [normalize_number(value) for value in extract_class_text(html, "span", "ball-red")]

    if len(numbers) != 6 or not red_balls:
        raise ValueError("sample HTML does not contain 6 regular balls and 1 special ball")

    return LottoResult(period=period, date=date, numbers=numbers, special=red_balls[0])


def fetch_html(url: str = DEFAULT_SOURCE_URL) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def parse_recent_page(html: str) -> list[LottoResult]:
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, flags=re.S | re.I)
    results: list[LottoResult] = []

    for row in rows:
        period = find_text(r'<td\s+class=["\']period["\'][^>]*>(.*?)</td>', row)
        date = find_text(r'<td\s+class=["\']date["\'][^>]*>(.*?)</td>', row)
        numbers_cell = find_text(r'<td\s+class=["\']numbers["\'][^>]*>(.*?)</td>', row)
        special_cell = find_text(r'<td\s+class=["\']special["\'][^>]*>(.*?)</td>', row)

        if not period or not date or not numbers_cell or not special_cell:
            continue

        raw_numbers = re.findall(r"\b\d{1,2}\b", numbers_cell)
        raw_special = re.findall(r"\b\d{1,2}\b", special_cell)
        if len(raw_numbers) < 6 or not raw_special:
            continue

        results.append(
            LottoResult(
                period=period,
                date=date,
                numbers=[normalize_number(value) for value in raw_numbers[:6]],
                special=normalize_number(raw_special[0]),
            )
        )

    if not results:
        raise ValueError("page format may have changed; no draw results were parsed")

    return results


def latest_result(url: str = DEFAULT_SOURCE_URL) -> LottoResult:
    return parse_recent_page(fetch_html(url))[0]


def result_by_period(period: str, url: str = DEFAULT_SOURCE_URL) -> LottoResult:
    normalized = period.strip()
    if normalized.isdigit() and len(normalized) == 6:
        normalized = "115000" + normalized[-3:]

    for result in parse_recent_page(fetch_html(url)):
        if result.period == normalized or result.period.endswith(period.strip()):
            return result

    raise LookupError(f"period not found in the recent results: {period}")


def format_result(result: LottoResult) -> str:
    return (
        f"Period: {result.period}\n"
        f"Date: {result.date}\n"
        f"Numbers: {' '.join(result.numbers)}\n"
        f"Special: {result.special}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print Taiwan Lotto draw results")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("basic", help="Parse the built-in sample HTML")

    latest = subparsers.add_parser("latest", help="Fetch and print the latest draw")
    latest.add_argument("--url", default=DEFAULT_SOURCE_URL, help="Recent draw source URL")

    period = subparsers.add_parser("period", help="Fetch and print a draw by period")
    period.add_argument("period", help="Period, for example 115000049 or 049")
    period.add_argument("--url", default=DEFAULT_SOURCE_URL, help="Recent draw source URL")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "basic":
            result = parse_sample_html()
        elif args.command == "latest":
            result = latest_result(args.url)
        elif args.command == "period":
            result = result_by_period(args.period, args.url)
        else:
            raise ValueError(f"unknown command: {args.command}")

        print(format_result(result))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
