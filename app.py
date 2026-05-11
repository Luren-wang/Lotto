from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import escape, unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SOURCE_URL = "https://lotto.hawo.tw/lotto/recent-50"
STUDENT_NAME = "B3201967 王仁為"


@dataclass(frozen=True)
class Draw:
    period: str
    date: str
    numbers: list[str]
    special: str


def fetch_draws() -> list[Draw]:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")
    return parse_draws(html)


def parse_draws(html: str) -> list[Draw]:
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, flags=re.S | re.I)
    draws: list[Draw] = []

    for row in rows:
        period = cell_text(row, "period")
        date = cell_text(row, "date")
        numbers_cell = cell_inner(row, "numbers")
        special_cell = cell_inner(row, "special")

        if not period or not date or not numbers_cell or not special_cell:
            continue

        numbers = extract_numbers(numbers_cell)
        special = extract_numbers(special_cell)
        if len(numbers) >= 6 and special:
            draws.append(Draw(period, date, numbers[:6], special[0]))

    if not draws:
        raise RuntimeError("no draw data found")
    return draws


def cell_inner(row: str, class_name: str) -> str:
    pattern = rf'<td\s+class=["\']{re.escape(class_name)}["\'][^>]*>(.*?)</td>'
    match = re.search(pattern, row, flags=re.S | re.I)
    return match.group(1) if match else ""


def cell_text(row: str, class_name: str) -> str:
    return clean_text(cell_inner(row, class_name))


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def extract_numbers(value: str) -> list[str]:
    return [f"{int(number):02d}" for number in re.findall(r"\b\d{1,2}\b", clean_text(value))]


def latest_draw() -> Draw:
    return fetch_draws()[0]


def draw_by_period(period: str) -> Draw | None:
    normalized = period.strip()
    if len(normalized) == 3 and normalized.isdigit():
        normalized = f"115000{normalized}"

    for draw in fetch_draws():
        if draw.period == normalized or draw.period.endswith(period.strip()):
            return draw
    return None


def draw_payload(draw: Draw) -> dict[str, object]:
    return {
        "period": draw.period,
        "date": draw.date,
        "numbers": draw.numbers,
        "special": draw.special,
    }


def render_page(draw: Draw | None, notice: str = "") -> str:
    notice_html = f'<p class="notice">{escape(notice)}</p>' if notice else ""
    result_html = ""
    if draw:
        balls = "".join(f'<span class="ball">{escape(number)}</span>' for number in draw.numbers)
        result_html = f"""
<p>第 <strong>{escape(draw.period)}</strong> 期，開獎日期：<strong>{escape(draw.date)}</strong></p>
<div class="balls">{balls}<span class="ball special">{escape(draw.special)}</span></div>
<p>一般號碼：{escape(" ".join(draw.numbers))}</p>
<p>特別號：{escape(draw.special)}</p>"""

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>大樂透開獎號碼</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;line-height:1.6}}
main{{max-width:720px;margin:auto}}
form{{display:flex;gap:.5rem;margin:1rem 0 1.25rem}}
input{{flex:1;padding:.7rem .8rem;border:1px solid #d1d5db;border-radius:.35rem;font:inherit}}
button{{padding:.7rem 1rem;border:0;border-radius:.35rem;background:#111827;color:#fff;font:inherit;font-weight:700;cursor:pointer}}
.notice{{padding:.75rem 1rem;border-radius:.35rem;background:#fef3c7;color:#92400e}}
.submission{{margin-top:2rem;padding-top:1.25rem;border-top:1px solid #e5e7eb}}
.balls{{display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0}}
.ball{{border-radius:999px;padding:.65rem .9rem;background:#f97316;color:#fff;font-weight:700}}
.special{{background:#dc2626}}
</style>
</head>
<body>
<main>
<h1>大樂透開獎號碼</h1>
<form method="get" action="/">
<input name="period" inputmode="numeric" placeholder="輸入期別，例如 115000049 或 049">
<button type="submit">查詢</button>
</form>
{notice_html}
{result_html}
<div class="submission">
<strong></strong>{escape(STUDENT_NAME)}
</div>
</main>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/health":
            self.send_text("ok")
            return

        if parsed.path == "/api/latest":
            self.send_json(draw_payload(latest_draw()))
            return

        if parsed.path == "/api/period":
            period = query.get("period", [""])[0].strip()
            draw = draw_by_period(period) if period else None
            if not draw:
                self.send_json({"error": "not found"}, status=404)
                return
            self.send_json(draw_payload(draw))
            return

        if parsed.path == "/":
            period = query.get("period", [""])[0].strip()
            if not period:
                try:
                    self.send_html(render_page(latest_draw()))
                except Exception:
                    self.send_html(render_page(None, "查詢不到，請重新輸入。"))
                return

            if not period.isdigit():
                self.send_html(render_page(None, "查詢不到，請重新輸入。"))
                return

            draw = draw_by_period(period)
            if draw:
                self.send_html(render_page(draw))
            else:
                self.send_html(render_page(None, "查詢不到，請重新輸入。"))
            return

        self.send_text("not found", status=404)

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_text(self, body: str, status: int = 200) -> None:
        self.send_response_with_body(body, "text/plain; charset=utf-8", status)

    def send_html(self, body: str, status: int = 200) -> None:
        self.send_response_with_body(body, "text/html; charset=utf-8", status)

    def send_json(self, payload: dict[str, object], status: int = 200) -> None:
        self.send_response_with_body(
            json.dumps(payload, ensure_ascii=False),
            "application/json; charset=utf-8",
            status,
        )

    def send_response_with_body(self, body: str, content_type: str, status: int) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Listening on 0.0.0.0:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
