from __future__ import annotations

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from lottery import latest_result, result_by_period


def result_payload(result):
    return {
        "period": result.period,
        "date": result.date,
        "numbers": result.numbers,
        "special": result.special,
    }


def html_page(payload: dict) -> str:
    period = payload["period"]
    date = payload["date"]
    numbers = " ".join(payload["numbers"])
    special = payload["special"]
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>大樂透開獎號碼</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.6; }}
    main {{ max-width: 720px; margin: 0 auto; }}
    .balls {{ display: flex; flex-wrap: wrap; gap: .5rem; margin: 1rem 0; }}
    .ball {{ border-radius: 999px; padding: .65rem .9rem; background: #f97316; color: white; font-weight: 700; }}
    .special {{ background: #dc2626; }}
    code {{ background: #f3f4f6; padding: .15rem .3rem; border-radius: .25rem; }}
  </style>
</head>
<body>
  <main>
    <h1>大樂透開獎號碼</h1>
    <p>第 <strong>{period}</strong> 期，開獎日期：<strong>{date}</strong></p>
    <div class="balls">
      {"".join(f'<span class="ball">{number}</span>' for number in payload["numbers"])}
      <span class="ball special">{special}</span>
    </div>
    <p>一般號碼：{numbers}</p>
    <p>特別號：{special}</p>
    <p>指定期別：<code>/?period=115000049</code> 或 <code>/?period=049</code></p>
    <p>JSON API：<code>/api/latest</code>、<code>/api/period?period=115000049</code></p>
  </main>
</body>
</html>"""


class LottoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        try:
            if parsed.path == "/health":
                self.send_text("ok")
                return

            if parsed.path == "/api/latest":
                self.send_json(result_payload(latest_result()))
                return

            if parsed.path == "/api/period":
                period = query.get("period", [""])[0]
                if not period:
                    self.send_json({"error": "missing period"}, status=400)
                    return
                self.send_json(result_payload(result_by_period(period)))
                return

            if parsed.path == "/":
                period = query.get("period", [""])[0]
                result = result_by_period(period) if period else latest_result()
                self.send_html(html_page(result_payload(result)))
                return

            self.send_json({"error": "not found"}, status=404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def log_message(self, format, *args):
        return

    def send_text(self, body: str, status: int = 200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, body: str, status: int = 200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: dict, status: int = 200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), LottoHandler)
    print(f"Listening on 0.0.0.0:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
