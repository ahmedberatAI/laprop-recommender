import argparse
import random
import re
import socket
import sys
import time
from datetime import datetime
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.amazon.com.tr"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

ACCEPT_LANGS = [
    "tr-TR,tr;q=0.9,en-US;q=0.7,en;q=0.6",
    "tr,en-US;q=0.7,en;q=0.5",
]


def log_line(message, log_fp=None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    print(line)
    if log_fp:
        log_fp.write(line + "\n")
        log_fp.flush()


def make_headers(referer=None):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice(ACCEPT_LANGS),
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def check_bot_or_captcha(html_text):
    if not html_text:
        return True
    l = html_text.lower()
    indicators = [
        "captcha",
        "bot check",
        "automated access",
        "unusual traffic",
        "verify you are a human",
        "guvenlik kontrol",
        "dogrulama",
        "/errors/validatecaptcha",
        "enter the characters you see below",
    ]
    return any(x in l for x in indicators)


def resolve_host(hostname, log_fp=None):
    try:
        infos = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
        ips = sorted({i[4][0] for i in infos})
        log_line(f"DNS resolve: {hostname} -> {', '.join(ips)}", log_fp)
    except Exception as exc:
        log_line(f"DNS resolve failed: {hostname} ({type(exc).__name__}: {exc})", log_fp)


def build_search_url(search_term, page_num):
    params = {"k": search_term, "page": page_num}
    if page_num > 1:
        params["ref"] = f"sr_pg_{page_num}"
    return f"{BASE_URL}/s?{urlencode(params)}"


def dump_html(text, out_path, log_fp=None):
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text or "")
        log_line(f"HTML saved: {out_path}", log_fp)
    except Exception as exc:
        log_line(f"Failed to save HTML: {type(exc).__name__}: {exc}", log_fp)


def describe_response(resp, log_fp=None):
    if not resp:
        log_line("Response: None", log_fp)
        return
    log_line(f"Status: {resp.status_code}", log_fp)
    log_line(f"Final URL: {resp.url}", log_fp)
    if resp.history:
        chain = " -> ".join([f"{r.status_code}:{r.url}" for r in resp.history] + [str(resp.status_code)])
        log_line(f"Redirect chain: {chain}", log_fp)
    log_line(f"Content-Type: {resp.headers.get('content-type')}", log_fp)
    log_line(f"Content-Length: {resp.headers.get('content-length')}", log_fp)


def count_cards(html_text):
    if not html_text:
        return 0
    soup = BeautifulSoup(html_text, "html.parser")
    cards = soup.find_all("div", {"data-component-type": "s-search-result"})
    if not cards:
        cards = soup.select('div[data-asin][data-index]')
    return len(cards)


def run_debug(args):
    log_fp = None
    if args.log_file:
        log_fp = open(args.log_file, "a", encoding="utf-8")

    try:
        log_line("Amazon scraper debug started", log_fp)
        log_line(f"Search term: {args.search}", log_fp)
        log_line(f"Pages: {args.start_page}..{args.end_page}", log_fp)
        log_line(f"Attempts per page: {args.attempts}", log_fp)
        log_line(f"Timeout: {args.timeout}s", log_fp)

        resolve_host("www.amazon.com.tr", log_fp)

        session = requests.Session()
        if args.http_proxy:
            session.proxies.update({"http": args.http_proxy})
        if args.https_proxy:
            session.proxies.update({"https": args.https_proxy})

        # Warm-up to get cookies
        session.headers.update(make_headers())
        try:
            log_line("Warm-up request: base URL", log_fp)
            t0 = time.perf_counter()
            r0 = session.get(BASE_URL, timeout=args.timeout)
            dt = time.perf_counter() - t0
            log_line(f"Warm-up elapsed: {dt:.2f}s", log_fp)
            describe_response(r0, log_fp)
            log_line(f"Cookies: {list(session.cookies.keys())}", log_fp)
        except requests.exceptions.RequestException as exc:
            log_line(f"Warm-up failed: {type(exc).__name__}: {exc}", log_fp)

        for page in range(args.start_page, args.end_page + 1):
            log_line("=" * 60, log_fp)
            url = build_search_url(args.search, page)
            log_line(f"Page {page} URL: {url}", log_fp)

            referer = None
            for attempt in range(1, args.attempts + 1):
                headers = make_headers(referer=referer)
                session.headers.clear()
                session.headers.update(headers)

                log_line(f"Attempt {attempt}/{args.attempts}", log_fp)
                t0 = time.perf_counter()
                try:
                    resp = session.get(url, timeout=args.timeout, allow_redirects=True)
                    dt = time.perf_counter() - t0
                    log_line(f"Elapsed: {dt:.2f}s", log_fp)
                    describe_response(resp, log_fp)

                    text = resp.text if resp is not None else ""
                    bot = check_bot_or_captcha(text)
                    cards = count_cards(text)
                    log_line(f"Cards found: {cards}", log_fp)
                    log_line(f"Bot/CAPTCHA detected: {bot}", log_fp)

                    if args.dump_html and (bot or resp.status_code != 200 or cards == 0):
                        dump_html(text, f"debug_page_{page}_attempt_{attempt}.html", log_fp)

                    if resp.status_code == 200 and not bot and cards > 0:
                        log_line("Page looks OK. Stopping attempts for this page.", log_fp)
                        break

                    referer = resp.url
                except requests.exceptions.RequestException as exc:
                    dt = time.perf_counter() - t0
                    log_line(f"Elapsed: {dt:.2f}s", log_fp)
                    log_line(f"Request failed: {type(exc).__name__}: {exc}", log_fp)

                if attempt < args.attempts:
                    sleep_for = args.wait + random.uniform(0.6, 1.8)
                    log_line(f"Sleep before next attempt: {sleep_for:.1f}s", log_fp)
                    time.sleep(sleep_for)
    finally:
        if log_fp:
            log_fp.close()


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Amazon scraper debug tool")
    parser.add_argument("--search", default="laptop", help="Search term")
    parser.add_argument("--start-page", type=int, default=1, help="Start page")
    parser.add_argument("--end-page", type=int, default=3, help="End page")
    parser.add_argument("--attempts", type=int, default=4, help="Attempts per page")
    parser.add_argument("--timeout", type=int, default=25, help="Request timeout in seconds")
    parser.add_argument("--wait", type=float, default=2.5, help="Base wait between attempts")
    parser.add_argument("--http-proxy", help="HTTP proxy URL")
    parser.add_argument("--https-proxy", help="HTTPS proxy URL")
    parser.add_argument("--dump-html", action="store_true", help="Save HTML for failed pages")
    parser.add_argument("--log-file", default="amazon_debug.log", help="Log file path")
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])
    run_debug(args)


if __name__ == "__main__":
    main()
