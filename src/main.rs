use std::env;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;

const SOURCE_URL: &str = "https://lotto.hawo.tw/lotto/recent-50";

#[derive(Clone, Debug)]
struct Draw {
    period: String,
    date: String,
    numbers: Vec<String>,
    special: String,
}

fn main() {
    let port = env::var("PORT").unwrap_or_else(|_| "10000".to_string());
    let addr = format!("0.0.0.0:{port}");
    let listener = TcpListener::bind(&addr).expect("failed to bind server port");
    println!("Listening on {addr}");

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                thread::spawn(move || handle(stream));
            }
            Err(err) => eprintln!("connection error: {err}"),
        }
    }
}

fn handle(mut stream: TcpStream) {
    let mut buffer = [0; 2048];
    let bytes = stream.read(&mut buffer).unwrap_or(0);
    let request = String::from_utf8_lossy(&buffer[..bytes]);
    let path = request
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .unwrap_or("/");

    let (status, content_type, body) = match route(path) {
        Ok(response) => response,
        Err(err) => (500, "application/json; charset=utf-8", format!(r#"{{"error":"{err}"}}"#)),
    };

    let response = format!(
        "HTTP/1.1 {status} OK\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.as_bytes().len()
    );
    let _ = stream.write_all(response.as_bytes());
}

fn route(path: &str) -> Result<(u16, &'static str, String), String> {
    let (route, query) = split_query(path);

    if route == "/health" {
        return Ok((200, "text/plain; charset=utf-8", "ok".to_string()));
    }

    if route == "/api/latest" {
        return latest().map(|draw| (200, "application/json; charset=utf-8", json(&draw)));
    }

    if route == "/api/period" {
        let period = query_param(query, "period").ok_or("missing period")?;
        return by_period(&period).map(|draw| (200, "application/json; charset=utf-8", json(&draw)));
    }

    if route == "/" {
        let period = query_param(query, "period").unwrap_or_default();
        let (draw, notice) = if period.trim().is_empty() {
            (latest().ok(), None)
        } else if !period.chars().all(|ch| ch.is_ascii_digit()) {
            (None, Some("查詢不到，請重新輸入。".to_string()))
        } else {
            match by_period(&period) {
                Ok(draw) => (Some(draw), None),
                Err(_) => (None, Some("查詢不到，請重新輸入。".to_string())),
            }
        };
        return Ok((200, "text/html; charset=utf-8", html(draw.as_ref(), notice.as_deref())));
    }

    Ok((404, "application/json; charset=utf-8", r#"{"error":"not found"}"#.to_string()))
}

fn latest() -> Result<Draw, String> {
    fetch_draws()?.into_iter().next().ok_or("no draw data found".to_string())
}

fn by_period(period: &str) -> Result<Draw, String> {
    let normalized = if period.len() == 3 && period.chars().all(|c| c.is_ascii_digit()) {
        format!("115000{period}")
    } else {
        period.to_string()
    };

    fetch_draws()?
        .into_iter()
        .find(|draw| draw.period == normalized || draw.period.ends_with(period))
        .ok_or_else(|| format!("period not found: {period}"))
}

fn fetch_draws() -> Result<Vec<Draw>, String> {
    let html = ureq::get(SOURCE_URL)
        .set("User-Agent", "Mozilla/5.0")
        .call()
        .map_err(|err| err.to_string())?
        .into_string()
        .map_err(|err| err.to_string())?;

    parse_draws(&html)
}

fn parse_draws(html: &str) -> Result<Vec<Draw>, String> {
    let mut draws = Vec::new();

    for chunk in html.split("<tr").skip(1) {
        let row = match chunk.split_once("</tr>") {
            Some((row, _)) => row,
            None => continue,
        };

        let period = match cell_text(row, "period") {
            Some(value) => value,
            None => continue,
        };
        let date = match cell_text(row, "date") {
            Some(value) => value,
            None => continue,
        };
        let number_cell = match cell_inner(row, "numbers") {
            Some(value) => value,
            None => continue,
        };
        let special_cell = match cell_inner(row, "special") {
            Some(value) => value,
            None => continue,
        };

        let numbers = extract_numbers(number_cell);
        let special = extract_numbers(special_cell).into_iter().next();
        if numbers.len() >= 6 {
            if let Some(special) = special {
                draws.push(Draw {
                    period,
                    date,
                    numbers: numbers.into_iter().take(6).collect(),
                    special,
                });
            }
        }
    }

    if draws.is_empty() {
        Err("page format changed; no draw rows parsed".to_string())
    } else {
        Ok(draws)
    }
}

fn cell_inner<'a>(row: &'a str, class_name: &str) -> Option<&'a str> {
    let marker = format!(r#"class="{class_name}""#);
    let start = row.find(&marker)?;
    let after_class = &row[start..];
    let content_start = after_class.find('>')? + 1;
    let content = &after_class[content_start..];
    let end = content.find("</td>")?;
    Some(&content[..end])
}

fn cell_text(row: &str, class_name: &str) -> Option<String> {
    cell_inner(row, class_name).map(strip_tags)
}

fn strip_tags(html: &str) -> String {
    let mut text = String::new();
    let mut in_tag = false;
    for ch in html.chars() {
        match ch {
            '<' => in_tag = true,
            '>' => in_tag = false,
            _ if !in_tag => text.push(ch),
            _ => {}
        }
    }
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn extract_numbers(text: &str) -> Vec<String> {
    let mut output = Vec::new();
    let mut current = String::new();

    for ch in strip_tags(text).chars() {
        if ch.is_ascii_digit() {
            current.push(ch);
        } else if !current.is_empty() {
            push_number(&mut output, &mut current);
        }
    }
    if !current.is_empty() {
        push_number(&mut output, &mut current);
    }

    output
}

fn push_number(output: &mut Vec<String>, current: &mut String) {
    if current.len() <= 2 {
        if let Ok(value) = current.parse::<u8>() {
            output.push(format!("{value:02}"));
        }
    }
    current.clear();
}

fn split_query(path: &str) -> (&str, &str) {
    match path.split_once('?') {
        Some((route, query)) => (route, query),
        None => (path, ""),
    }
}

fn query_param(query: &str, key: &str) -> Option<String> {
    for pair in query.split('&') {
        let (name, value) = pair.split_once('=').unwrap_or((pair, ""));
        if name == key {
            return Some(value.replace("%2F", "/").replace("%20", " "));
        }
    }
    None
}

fn json(draw: &Draw) -> String {
    format!(
        r#"{{"period":"{}","date":"{}","numbers":["{}"],"special":"{}"}}"#,
        draw.period,
        draw.date,
        draw.numbers.join(r#"",""#),
        draw.special
    )
}

fn html(draw: Option<&Draw>, notice: Option<&str>) -> String {
    let notice_html = notice
        .map(|message| format!(r#"<p class="notice">{message}</p>"#))
        .unwrap_or_default();
    let result_html = match draw {
        Some(draw) => {
            let balls = draw
                .numbers
                .iter()
                .map(|number| format!(r#"<span class="ball">{number}</span>"#))
                .collect::<Vec<_>>()
                .join("");
            format!(
                r#"<p>第 <strong>{}</strong> 期，開獎日期：<strong>{}</strong></p>
<div class="balls">{}<span class="ball special">{}</span></div>
<p>一般號碼：{}</p>
<p>特別號：{}</p>"#,
                draw.period,
                draw.date,
                balls,
                draw.special,
                draw.numbers.join(" "),
                draw.special
            )
        }
        None => String::new(),
    };

    format!(
        r#"<!doctype html>
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
{}
{}
</main>
</body>
</html>"#,
        notice_html,
        result_html
    )
}
