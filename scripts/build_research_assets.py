from __future__ import annotations

import csv
import datetime as dt
import html
import json
import math
import re
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MEDIA = ROOT / "media"
OUT = ROOT / "outputs"

RUN_DATE = "2026-05-28"


def ensure_dirs() -> None:
    for path in (DATA, MEDIA, OUT):
        path.mkdir(parents=True, exist_ok=True)


def get_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def to_num(token: str | None) -> float | None:
    if token is None:
        return None
    s = token.strip().replace("$", "").replace(",", "")
    if s in {"", "n/a", "N/A"}:
        return None
    mult = 1.0
    if s.endswith("T"):
        mult = 1_000.0
        s = s[:-1]
    elif s.endswith("B"):
        mult = 1.0
        s = s[:-1]
    elif s.endswith("M"):
        mult = 0.001
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def compact_text(raw_html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw_html)
    return html.unescape(re.sub(r"\s+", " ", text))


def parse_stat(text: str, label: str) -> float | None:
    m = re.search(rf"{re.escape(label)}\s+(-?\$?[\d.,]+[BTM]?|-?\d+\.\d+|-?\d+)", text)
    return to_num(m.group(1)) if m else None


def fetch_stockanalysis(symbols: list[str]) -> list[dict]:
    rows = []
    for symbol in symbols:
        url = f"https://stockanalysis.com/stocks/{symbol.lower()}/statistics/"
        try:
            text = compact_text(get_url(url))
        except Exception:
            text = ""
        price = fetch_yahoo_quote(symbol).get("regularMarketPrice")
        rows.append(
            {
                "ticker": symbol,
                "company": {
                    "FSLR": "First Solar",
                    "ENPH": "Enphase Energy",
                    "SEDG": "SolarEdge Technologies",
                    "CSIQ": "Canadian Solar",
                    "JKS": "JinkoSolar",
                    "ARRY": "Array Technologies",
                    "SHLS": "Shoals Technologies",
                    "NXT": "Nextpower",
                    "RUN": "Sunrun",
                }.get(symbol, symbol),
                "segment": {
                    "FSLR": "CdTe modules, U.S. manufacturing",
                    "ENPH": "microinverters/storage",
                    "SEDG": "inverters/optimizer",
                    "CSIQ": "modules/projects/storage",
                    "JKS": "modules/global manufacturing",
                    "ARRY": "trackers",
                    "SHLS": "EBOS",
                    "NXT": "trackers/software",
                    "RUN": "residential solar/service",
                }.get(symbol, ""),
                "price_usd": price,
                "market_cap_usd_bn": parse_stat(text, "Market Cap"),
                "enterprise_value_usd_bn": parse_stat(text, "Enterprise Value"),
                "pe_ttm": parse_stat(text, "PE Ratio"),
                "forward_pe": parse_stat(text, "Forward PE"),
                "ps_ttm": parse_stat(text, "PS Ratio"),
                "ev_sales_ttm": parse_stat(text, "EV / Sales"),
                "ev_ebitda_ttm": parse_stat(text, "EV / EBITDA"),
                "source_id": "S12",
                "quote_source_id": "S11",
                "note": "Secondary market data snapshot; FSLR valuation cross-checks also use company filings and guidance.",
            }
        )
    return rows


def fetch_yahoo_quote(symbol: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d"
    try:
        data = json.loads(get_url(url))
        return data["chart"]["result"][0]["meta"]
    except Exception:
        return {}


def fetch_history(symbol: str, start: str, end: str) -> list[dict]:
    start_ts = int(dt.datetime.strptime(start, "%Y-%m-%d").timestamp())
    end_dt = dt.datetime.strptime(end, "%Y-%m-%d") + dt.timedelta(days=1)
    end_ts = int(end_dt.timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={start_ts}&period2={end_ts}&interval=1d&events=history&includeAdjustedClose=true"
    )
    data = json.loads(get_url(url))
    result = data["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    adj = result["indicators"].get("adjclose", [{}])[0].get("adjclose", [])
    rows = []
    for i, ts in enumerate(result["timestamp"]):
        date = dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        close = quote["close"][i]
        if close is None:
            continue
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": quote["open"][i],
                "high": quote["high"][i],
                "low": quote["low"][i],
                "close": close,
                "adj_close": adj[i] if i < len(adj) else close,
                "volume": quote["volume"][i],
                "source_id": "S11",
            }
        )
    return rows


def close_before_on_after(history: list[dict], event_date: str, timing: str) -> tuple[dict, dict]:
    rows = [r for r in history if r["date"] <= event_date]
    after_rows = [r for r in history if r["date"] >= event_date]
    if timing == "after_close":
        before = rows[-1]
        later = [r for r in history if r["date"] > event_date][0]
    else:
        before = rows[-2] if rows and rows[-1]["date"] == event_date else rows[-1]
        later = after_rows[0]
    return before, later


def pct(a: float, b: float) -> float:
    return (b / a - 1.0) * 100.0


def write_csv(name: str, rows: list[dict]) -> None:
    if not rows:
        return
    path = DATA / name
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(name: str, obj) -> None:
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def font_setup():
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def load_font(path: str | None, size: int, bold: bool = False):
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill: str, max_width: int, line_gap: int = 8):
    x, y = xy
    line = ""
    for ch in text:
        test = line + ch
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            draw.text((x, y), line, font=font, fill=fill)
            y += font.size + line_gap
            line = ch
    if line:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def save_card(filename: str, title: str, subtitle: str, bullets: list[str], font_path: str | None, accent: str = "#0E7C66") -> None:
    img = Image.new("RGB", (1600, 900), "#F6F7F2")
    draw = ImageDraw.Draw(img)
    title_font = load_font(font_path, 48)
    sub_font = load_font(font_path, 26)
    bullet_font = load_font(font_path, 30)
    small_font = load_font(font_path, 17)
    draw.rectangle((0, 0, 1600, 64), fill=accent)
    draw.text((88, 142), title, font=title_font, fill="#10231F")
    draw_wrapped(draw, (92, 220), subtitle, sub_font, "#43524C", 1380)
    y = 335
    for b in bullets:
        draw.rounded_rectangle((96, y - 36, 1504, y + 66), radius=20, fill="#FFFFFF", outline="#D8DDD4", width=2)
        draw_wrapped(draw, (138, y - 8), b, bullet_font, "#172820", 1300, line_gap=4)
        y += 128
    draw.text((96, 824), "First Solar (FSLR) 深度研究 | 数据截至 2026-05-28 | 来源见项目 data/sources.csv",
              font=small_font, fill="#6B746F")
    img.save(MEDIA / filename)


def save_bar_card(filename: str, title: str, subtitle: str, labels: list[str], values: list[float], suffix: str, font_path: str | None, accent: str):
    img = Image.new("RGB", (1600, 900), "#F7F5EF")
    draw = ImageDraw.Draw(img)
    title_font = load_font(font_path, 46)
    sub_font = load_font(font_path, 24)
    label_font = load_font(font_path, 21)
    value_font = load_font(font_path, 25)
    small_font = load_font(font_path, 17)
    draw.text((88, 86), title, font=title_font, fill="#10231F")
    draw_wrapped(draw, (92, 157), subtitle, sub_font, "#4E5C55", 1380)
    chart = (130, 270, 1490, 710)
    min_v = min(0, min(values))
    max_v = max(0, max(values))
    span = max_v - min_v if max_v != min_v else 1
    zero_y = int(chart[3] - (0 - min_v) / span * (chart[3] - chart[1]))
    draw.line((chart[0], zero_y, chart[2], zero_y), fill="#38433E", width=2)
    n = len(labels)
    gap = 38
    bar_w = int((chart[2] - chart[0] - gap * (n + 1)) / n)
    for i, (lab, val) in enumerate(zip(labels, values)):
        x0 = chart[0] + gap + i * (bar_w + gap)
        x1 = x0 + bar_w
        y_val = int(chart[3] - (val - min_v) / span * (chart[3] - chart[1]))
        color = accent if val >= 0 else "#B5483A"
        y0, y1 = (y_val, zero_y) if val >= 0 else (zero_y, y_val)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=12, fill=color)
        val_text = f"${val:.0f}" if suffix == "$" else f"{val:.1f}{suffix}"
        tw = draw.textlength(val_text, font=value_font)
        ty = y0 - 38 if val >= 0 else y1 + 8
        draw.text((x0 + (bar_w - tw) / 2, ty), val_text, font=value_font, fill="#10231F")
        lw = draw.textlength(lab, font=label_font)
        draw.text((x0 + (bar_w - lw) / 2, chart[3] + 28), lab, font=label_font, fill="#24342D")
    note = (
        "注：情景价格基于 FY2026 EBITDA、EV/EBITDA 和净现金测算；不是目标价。"
        if suffix == "$"
        else "注：市场反应为事件窗口 close-to-close，alpha = FSLR - TAN。来源：Yahoo Finance chart API。"
    )
    draw.text((130, 805), note, font=small_font, fill="#6B746F")
    img.save(MEDIA / filename)


def save_tweet_card(
    filename: str,
    title: str,
    kicker: str,
    points: list[tuple[str, str]],
    font_path: str | None,
    accent: str = "#0E7C66",
    footer: str = "First Solar (FSLR) 深度研究 | 数据截至 2026-05-28 | 来源见 data/sources.csv",
) -> None:
    img = Image.new("RGB", (1600, 900), "#F7F5EF")
    draw = ImageDraw.Draw(img)
    title_font = load_font(font_path, 46)
    kicker_font = load_font(font_path, 23)
    heading_font = load_font(font_path, 28)
    body_font = load_font(font_path, 24)
    footer_font = load_font(font_path, 16)

    draw.rectangle((0, 0, 1600, 74), fill=accent)
    draw.text((92, 112), title, font=title_font, fill="#10231F")
    draw_wrapped(draw, (96, 182), kicker, kicker_font, "#51615A", 1340, line_gap=6)

    y = 292
    box_h = 118 if len(points) >= 4 else 142
    for i, (heading, body) in enumerate(points, start=1):
        y0 = y + (i - 1) * (box_h + 18)
        draw.rounded_rectangle((96, y0, 1504, y0 + box_h), radius=18, fill="#FFFFFF", outline="#D8DDD4", width=2)
        draw.rounded_rectangle((118, y0 + 22, 176, y0 + 80), radius=14, fill=accent)
        num = str(i)
        tw = draw.textlength(num, font=heading_font)
        draw.text((147 - tw / 2, y0 + 33), num, font=heading_font, fill="#FFFFFF")
        draw.text((204, y0 + 20), heading, font=heading_font, fill="#10231F")
        draw_wrapped(draw, (204, y0 + 61), body, body_font, "#2C3B35", 1210, line_gap=5)

    draw.text((96, 836), footer, font=footer_font, fill="#6B746F")
    img.save(MEDIA / filename)


def save_tweet_valuation_card(
    filename: str,
    current_price: float,
    scenarios: list[dict],
    font_path: str | None,
) -> None:
    img = Image.new("RGB", (1600, 900), "#F7F5EF")
    draw = ImageDraw.Draw(img)
    title_font = load_font(font_path, 46)
    sub_font = load_font(font_path, 23)
    label_font = load_font(font_path, 24)
    value_font = load_font(font_path, 32)
    small_font = load_font(font_path, 16)
    colors = {"Bear": "#B5483A", "Base": "#8A5B20", "Bull": "#0E7C66"}

    draw.rectangle((0, 0, 1600, 74), fill="#365F91")
    draw.text((92, 112), "估值：不是便宜，但偏买", font=title_font, fill="#10231F")
    draw.text((96, 182), "base case 低于当前价；主动建仓靠质量、净现金、backlog 和可验证 bull case 触发器", font=sub_font, fill="#51615A")

    chart = (150, 310, 1450, 690)
    values = [s["implied_price_usd"] for s in scenarios] + [current_price]
    max_v = max(values) * 1.15
    baseline = chart[3]
    bar_w = 190
    gap = 105
    labels = [s["scenario"] for s in scenarios] + ["Current"]
    display_values = [s["implied_price_usd"] for s in scenarios] + [current_price]
    for i, (lab, val) in enumerate(zip(labels, display_values)):
        x0 = chart[0] + i * (bar_w + gap)
        x1 = x0 + bar_w
        y0 = int(baseline - (val / max_v) * (chart[3] - chart[1]))
        color = colors.get(lab, "#10231F")
        draw.rounded_rectangle((x0, y0, x1, baseline), radius=18, fill=color)
        price_text = f"${val:.0f}"
        tw = draw.textlength(price_text, font=value_font)
        draw.text((x0 + (bar_w - tw) / 2, y0 - 45), price_text, font=value_font, fill="#10231F")
        lw = draw.textlength(lab, font=label_font)
        draw.text((x0 + (bar_w - lw) / 2, baseline + 28), lab, font=label_font, fill="#24342D")
        if lab in {"Bear", "Base", "Bull"}:
            vs = val / current_price - 1
            vs_text = f"{vs:+.1%} vs current"
            sw = draw.textlength(vs_text, font=small_font)
            draw.text((x0 + (bar_w - sw) / 2, baseline + 66), vs_text, font=small_font, fill="#6B746F")

    draw.line((chart[0] - 20, baseline, chart[2], baseline), fill="#38433E", width=2)
    draw.text((96, 836), "情景价格基于 FY2026 EBITDA、EV/EBITDA 和净现金测算；不是目标价。", font=small_font, fill="#6B746F")
    img.save(MEDIA / filename)


def main() -> None:
    ensure_dirs()
    font_path = font_setup()

    sources = [
        {"source_id": "S1", "title": "First Solar Q1 2026 earnings release, furnished as SEC 8-K Exhibit 99.1", "publisher": "First Solar / SEC", "date": "2026-04-30", "url": "https://www.sec.gov/Archives/edgar/data/1274494/000127449426000108/ex991pressreleaseq1-2026.htm", "source_type": "company filing", "used_for": "Q1 revenue, EPS, EBITDA, cash, debt, guidance, backlog", "quality": "primary"},
        {"source_id": "S2", "title": "First Solar Form 10-Q for quarter ended March 31, 2026", "publisher": "SEC", "date": "2026-04-30", "url": "https://www.sec.gov/Archives/edgar/data/1274494/000127449426000109/fslr-20260331.htm", "source_type": "SEC filing", "used_for": "Q1 financial statements, capacity and policy-risk wording", "quality": "primary"},
        {"source_id": "S3", "title": "First Solar Q1 2026 earnings presentation", "publisher": "First Solar", "date": "2026-04-30", "url": "https://s202.q4cdn.com/499595574/files/doc_financials/2026/q1/Q1-26-Earnings-Presentation-vf-Secured.pdf", "source_type": "company presentation", "used_for": "bookings, backlog, guide ranges, capacity, 45X guide, shipment and sales volume", "quality": "primary"},
        {"source_id": "S4", "title": "First Solar Form 10-K for fiscal year 2025", "publisher": "SEC", "date": "2026-02-24", "url": "https://www.sec.gov/Archives/edgar/data/1274494/000127449426000021/fslr-20251231.htm", "source_type": "SEC filing", "used_for": "FY2023-FY2025 financials, cash flow, operating drivers", "quality": "primary"},
        {"source_id": "S5", "title": "First Solar Q4/FY2025 earnings release, furnished as SEC 8-K Exhibit 99.1", "publisher": "First Solar / SEC", "date": "2026-02-24", "url": "https://www.sec.gov/Archives/edgar/data/1274494/000127449426000020/ex991pressreleaseq4-2025fi.htm", "source_type": "company filing", "used_for": "FY2025 results, 2026 guide baseline, year-end backlog", "quality": "primary"},
        {"source_id": "S6", "title": "IRS final regulations for Section 45X advanced manufacturing production credit", "publisher": "IRS", "date": "2024-12-16", "url": "https://www.irs.gov/irb/2024-51_IRB/index.html", "source_type": "official policy", "used_for": "45X credit qualification and solar module components", "quality": "primary"},
        {"source_id": "S7", "title": "IRS clean energy provisions of the One Big Beautiful Bill Act", "publisher": "IRS", "date": "2025-08-28", "url": "https://www.irs.gov/credits-deductions/one-big-beautiful-bill-act-provisions-for-individuals-and-businesses", "source_type": "official policy", "used_for": "post-OBBBA clean-energy-credit constraints and FEOC/PFE monitor", "quality": "primary"},
        {"source_id": "S8", "title": "Commerce final determinations in solar cells from Cambodia, Malaysia, Thailand and Vietnam", "publisher": "U.S. Department of Commerce", "date": "2025-04-21", "url": "https://www.trade.gov/press-release/us-department-commerce-announces-final-determinations-antidumping-and-countervailing", "source_type": "official trade policy", "used_for": "AD/CVD tariff risk and domestic supply-demand context", "quality": "primary"},
        {"source_id": "S9", "title": "BIS Section 232 investigations page", "publisher": "U.S. Bureau of Industry and Security", "date": "2026-05-28", "url": "https://www.bis.doc.gov/index.php/232", "source_type": "official trade policy", "used_for": "Section 232 polysilicon/derivatives status tracker", "quality": "primary"},
        {"source_id": "S10", "title": "USITC Section 337 TOPCon solar cells investigation docket", "publisher": "U.S. International Trade Commission", "date": "2026-03-26", "url": "https://www.usitc.gov/press_room/news_release/2026/er0326_67276.htm", "source_type": "official litigation/regulatory", "used_for": "patent/import catalyst and policy risk tracker", "quality": "primary"},
        {"source_id": "S11", "title": "Yahoo Finance chart API and quote pages", "publisher": "Yahoo Finance", "date": RUN_DATE, "url": "https://finance.yahoo.com/quote/FSLR", "source_type": "market data", "used_for": "current quote and event-window close-to-close market reactions", "quality": "market data"},
        {"source_id": "S12", "title": "StockAnalysis valuation statistics pages", "publisher": "StockAnalysis", "date": RUN_DATE, "url": "https://stockanalysis.com/stocks/fslr/statistics/", "source_type": "secondary market data", "used_for": "market cap, EV, peer valuation snapshots", "quality": "secondary"},
        {"source_id": "S13", "title": "First Solar 8-K: $1.5B senior unsecured revolving credit facility", "publisher": "SEC", "date": "2026-02-19", "url": "https://www.sec.gov/Archives/edgar/data/1274494/000127449426000016/fslr-20260213.htm", "source_type": "SEC filing", "used_for": "liquidity and balance-sheet catalyst", "quality": "primary"},
        {"source_id": "S14", "title": "USITC sunset reviews: crystalline silicon photovoltaic cells and modules from China and Taiwan", "publisher": "U.S. International Trade Commission", "date": "2026-05-27", "url": "https://www.usitc.gov/press_room/news_release/2026/er0527_67584.htm", "source_type": "official trade policy", "used_for": "tariff continuation catalyst", "quality": "primary"},
    ]

    financials = [
        {"category": "Income statement", "metric": "Net sales", "unit": "USD mn", "2023A": 3318.602, "2024A": 4206.289, "2025A": 5219.376, "Q1_2025A": 844.568, "Q1_2026A": 1044.240, "FY2026_guidance_mid": 5050.0, "source_id": "S1;S3;S4;S5", "note": "2026 guidance midpoint of $4.9-$5.2bn."},
        {"category": "Income statement", "metric": "Gross profit", "unit": "USD mn", "2023A": 1300.679, "2024A": 1857.864, "2025A": 2120.339, "Q1_2025A": 344.403, "Q1_2026A": 486.131, "FY2026_guidance_mid": 2500.0, "source_id": "S1;S3;S4;S5", "note": "2026 guidance midpoint of $2.4-$2.6bn."},
        {"category": "Income statement", "metric": "Gross margin", "unit": "%", "2023A": 39.19, "2024A": 44.17, "2025A": 40.63, "Q1_2025A": 40.78, "Q1_2026A": 46.55, "FY2026_guidance_mid": 49.50, "source_id": "S1;S4", "note": "Calculated from net sales and gross profit."},
        {"category": "Income statement", "metric": "Operating income", "unit": "USD mn", "2023A": 857.266, "2024A": 1394.420, "2025A": 1596.864, "Q1_2025A": 221.244, "Q1_2026A": 345.303, "FY2026_guidance_mid": "", "source_id": "S1;S4", "note": ""},
        {"category": "Income statement", "metric": "Net income", "unit": "USD mn", "2023A": 830.777, "2024A": 1292.044, "2025A": 1528.229, "Q1_2025A": 209.535, "Q1_2026A": 346.619, "FY2026_guidance_mid": "", "source_id": "S1;S4", "note": ""},
        {"category": "Income statement", "metric": "Diluted EPS", "unit": "USD/share", "2023A": 7.74, "2024A": 12.02, "2025A": 14.21, "Q1_2025A": 1.95, "Q1_2026A": 3.22, "FY2026_guidance_mid": "", "source_id": "S1;S4", "note": ""},
        {"category": "Cash flow", "metric": "Operating cash flow", "unit": "USD mn", "2023A": 602.260, "2024A": 1217.999, "2025A": 2057.105, "Q1_2025A": -607.982, "Q1_2026A": -214.866, "FY2026_guidance_mid": "", "source_id": "S2;S4", "note": "Q1 seasonality and working-capital timing matter."},
        {"category": "Cash flow", "metric": "Capex / PP&E purchases", "unit": "USD mn", "2023A": 1386.775, "2024A": 1526.076, "2025A": 869.875, "Q1_2025A": 205.966, "Q1_2026A": 118.529, "FY2026_guidance_mid": 900.0, "source_id": "S2;S3;S4", "note": "2026 guidance midpoint of $0.8-$1.0bn."},
        {"category": "Non-GAAP", "metric": "Adjusted EBITDA", "unit": "USD mn", "2023A": "", "2024A": "", "2025A": "", "Q1_2025A": 379.180, "Q1_2026A": 519.807, "FY2026_guidance_mid": 2700.0, "source_id": "S1;S3", "note": "2026 guidance midpoint of $2.6-$2.8bn."},
        {"category": "Business KPI", "metric": "Module production", "unit": "GWdc", "2023A": "", "2024A": "", "2025A": 17.5, "Q1_2025A": "", "Q1_2026A": 4.3, "FY2026_guidance_mid": "", "source_id": "S2;S4", "note": "Production, not shipment."},
        {"category": "Business KPI", "metric": "Module sold", "unit": "GWdc", "2023A": "", "2024A": "", "2025A": 16.7, "Q1_2025A": "", "Q1_2026A": 3.8, "FY2026_guidance_mid": 17.6, "source_id": "S1;S2;S3;S4", "note": "2026 guidance midpoint of 17.0-18.2GW sold."},
        {"category": "Business KPI", "metric": "Contracted backlog", "unit": "GWdc", "2023A": "", "2024A": "", "2025A": 48.8, "Q1_2025A": "", "Q1_2026A": 47.9, "FY2026_guidance_mid": "", "source_id": "S1;S3;S5", "note": "Backlog is contracted future volume, not current revenue."},
        {"category": "Business KPI", "metric": "Backlog value", "unit": "USD bn", "2023A": "", "2024A": "", "2025A": 14.6, "Q1_2025A": "", "Q1_2026A": 14.4, "FY2026_guidance_mid": "", "source_id": "S1;S3;S5", "note": "Backlog dollar value includes future contracted net sales."},
        {"category": "Business KPI", "metric": "Bookings YTD", "unit": "GWdc", "2023A": "", "2024A": "", "2025A": "", "Q1_2025A": "", "Q1_2026A": 3.7, "FY2026_guidance_mid": "", "source_id": "S1;S3", "note": "3.7GW net bookings since prior earnings call."},
        {"category": "Balance sheet", "metric": "Cash and marketable securities", "unit": "USD mn", "2023A": 2269.609, "2024A": 1267.781, "2025A": 1993.961, "Q1_2025A": 1261.902, "Q1_2026A": 2426.579, "FY2026_guidance_mid": "", "source_id": "S2;S4", "note": "Includes cash, cash equivalents, marketable securities and restricted cash/securities."},
        {"category": "Balance sheet", "metric": "Debt", "unit": "USD mn", "2023A": 562.063, "2024A": 540.284, "2025A": 540.001, "Q1_2025A": 540.124, "Q1_2026A": 425.753, "FY2026_guidance_mid": "", "source_id": "S2;S4", "note": "Current debt + long-term debt."},
        {"category": "Balance sheet", "metric": "Net cash", "unit": "USD mn", "2023A": 1707.546, "2024A": 727.497, "2025A": 1453.960, "Q1_2025A": 721.778, "Q1_2026A": 2000.826, "FY2026_guidance_mid": "", "source_id": "S1;S2;S4", "note": "Cash and marketable securities less debt."},
    ]

    key_metrics = {
        "current_price_usd": fetch_yahoo_quote("FSLR").get("regularMarketPrice", 273.67),
        "current_price_time": fetch_yahoo_quote("FSLR").get("regularMarketTime"),
        "diluted_shares_mn_q1_2026": 107.615,
        "market_cap_usd_bn_company_basis": None,
        "net_cash_usd_bn_q1_2026": 2.000826,
        "fy2026_sales_mid_usd_bn": 5.050,
        "fy2026_ebitda_mid_usd_bn": 2.700,
        "backlog_gw": 47.9,
        "backlog_value_usd_bn": 14.4,
        "backlog_asp_usd_per_w": 14.4 / 47.9,
        "ttm_eps_usd": 14.21 - 1.95 + 3.22,
    }
    key_metrics["market_cap_usd_bn_company_basis"] = key_metrics["current_price_usd"] * key_metrics["diluted_shares_mn_q1_2026"] / 1000
    key_metrics["ev_usd_bn_company_basis"] = key_metrics["market_cap_usd_bn_company_basis"] - key_metrics["net_cash_usd_bn_q1_2026"]
    key_metrics["pe_ttm_company_basis"] = key_metrics["current_price_usd"] / key_metrics["ttm_eps_usd"]
    key_metrics["ev_sales_fy2026_mid"] = key_metrics["ev_usd_bn_company_basis"] / key_metrics["fy2026_sales_mid_usd_bn"]
    key_metrics["ev_ebitda_fy2026_mid"] = key_metrics["ev_usd_bn_company_basis"] / key_metrics["fy2026_ebitda_mid_usd_bn"]

    peers = fetch_stockanalysis(["FSLR", "ENPH", "SEDG", "CSIQ", "JKS", "ARRY", "SHLS", "NXT", "RUN"])
    for r in peers:
        if r["ticker"] == "FSLR":
            r["price_usd"] = round(key_metrics["current_price_usd"], 3)
            r["market_cap_usd_bn"] = round(key_metrics["market_cap_usd_bn_company_basis"], 2)
            r["enterprise_value_usd_bn"] = round(key_metrics["ev_usd_bn_company_basis"], 2)
            r["pe_ttm"] = round(key_metrics["pe_ttm_company_basis"], 2)
            r["ev_sales_ttm"] = round(
                key_metrics["ev_usd_bn_company_basis"] / ((5219.376 - 844.568 + 1044.240) / 1000), 2
            )
            r["market_cap_company_basis_usd_bn"] = round(key_metrics["market_cap_usd_bn_company_basis"], 2)
            r["ev_company_basis_usd_bn"] = round(key_metrics["ev_usd_bn_company_basis"], 2)
            r["pe_ttm_company_basis"] = round(key_metrics["pe_ttm_company_basis"], 2)
            r["ev_sales_fy2026_mid_company_basis"] = round(key_metrics["ev_sales_fy2026_mid"], 2)
            r["ev_ebitda_fy2026_mid_company_basis"] = round(key_metrics["ev_ebitda_fy2026_mid"], 2)
            r["note"] = "FSLR market cap/EV/PE use company-basis current price, Q1 diluted shares and Q1 net cash; peer multiples are directional only."
        else:
            r["market_cap_company_basis_usd_bn"] = ""
            r["ev_company_basis_usd_bn"] = ""
            r["pe_ttm_company_basis"] = ""
            r["ev_sales_fy2026_mid_company_basis"] = ""
            r["ev_ebitda_fy2026_mid_company_basis"] = ""
            r["note"] = "Directional peer only: business model, margin structure, policy exposure and balance sheet differ from FSLR."

    scenarios = [
        {"scenario": "Bear", "description": "政策支持边际变弱，新增订单价格走低，产能爬坡和现金税抵消部分 45X 好处", "fy2026_ebitda_usd_bn": 2.30, "ev_ebitda_multiple": 8.0, "net_cash_usd_bn": key_metrics["net_cash_usd_bn_q1_2026"], "shares_mn": key_metrics["diluted_shares_mn_q1_2026"], "implied_price_usd": (2.30 * 8.0 + key_metrics["net_cash_usd_bn_q1_2026"]) * 1000 / key_metrics["diluted_shares_mn_q1_2026"], "source_id": "S1;S3;S12", "note": "Multiple below current FSLR TTM EV/EBITDA and around cyclical de-rating case."},
        {"scenario": "Base", "description": "2026 指引基本兑现，45X 现金/税务收益可持续，backlog ASP 稳住但不显著扩张", "fy2026_ebitda_usd_bn": 2.70, "ev_ebitda_multiple": 10.0, "net_cash_usd_bn": key_metrics["net_cash_usd_bn_q1_2026"], "shares_mn": key_metrics["diluted_shares_mn_q1_2026"], "implied_price_usd": (2.70 * 10.0 + key_metrics["net_cash_usd_bn_q1_2026"]) * 1000 / key_metrics["diluted_shares_mn_q1_2026"], "source_id": "S1;S3;S12", "note": "Uses FY2026 adjusted EBITDA midpoint."},
        {"scenario": "Bull", "description": "Section 232/贸易保护强化美国供应稀缺性，CuRe/Series 7 量产改善效率，2027-2028 新单价格好于预期", "fy2026_ebitda_usd_bn": 3.20, "ev_ebitda_multiple": 12.0, "net_cash_usd_bn": key_metrics["net_cash_usd_bn_q1_2026"], "shares_mn": key_metrics["diluted_shares_mn_q1_2026"], "implied_price_usd": (3.20 * 12.0 + key_metrics["net_cash_usd_bn_q1_2026"]) * 1000 / key_metrics["diluted_shares_mn_q1_2026"], "source_id": "S1;S3;S8;S9;S10", "note": "Requires policy and booking data共同验证，不应只靠叙事给高倍数."},
    ]

    history_fslr = fetch_history("FSLR", "2025-01-01", RUN_DATE)
    history_tan = fetch_history("TAN", "2025-01-01", RUN_DATE)
    by_symbol_history = {"FSLR": history_fslr, "TAN": history_tan}
    events = [
        {"event_date": "2025-04-21", "event": "Commerce 对东南亚太阳能电池/组件 AD/CVD 作出最终裁定", "type": "trade policy", "timing": "intraday_or_before_close", "source_id": "S8"},
        {"event_date": "2026-02-19", "event": "$1.5bn senior unsecured revolver 披露", "type": "liquidity", "timing": "after_close", "source_id": "S13"},
        {"event_date": "2026-02-24", "event": "FY2025/Q4 earnings + 2026 guidance", "type": "earnings", "timing": "after_close", "source_id": "S5"},
        {"event_date": "2026-03-26", "event": "USITC 启动 TOPCon Section 337 调查", "type": "trade/IP", "timing": "intraday_or_before_close", "source_id": "S10"},
        {"event_date": "2026-04-30", "event": "Q1 2026 earnings，维持全年指引", "type": "earnings", "timing": "after_close", "source_id": "S1"},
        {"event_date": "2026-05-27", "event": "USITC 对中台晶硅电池/组件 sunset review 表态", "type": "trade policy", "timing": "intraday_or_before_close", "source_id": "S14"},
    ]
    reactions = []
    for e in events:
        b_f, a_f = close_before_on_after(history_fslr, e["event_date"], e["timing"])
        b_t, a_t = close_before_on_after(history_tan, e["event_date"], e["timing"])
        f_ret = pct(b_f["close"], a_f["close"])
        t_ret = pct(b_t["close"], a_t["close"])
        reactions.append(
            {
                "event_date": e["event_date"],
                "event": e["event"],
                "type": e["type"],
                "timing": e["timing"],
                "before_date": b_f["date"],
                "after_date": a_f["date"],
                "fslr_close_before": round(b_f["close"], 2),
                "fslr_close_after": round(a_f["close"], 2),
                "fslr_return_pct": round(f_ret, 2),
                "tan_return_pct": round(t_ret, 2),
                "alpha_vs_tan_pct": round(f_ret - t_ret, 2),
                "source_id": e["source_id"] + ";S11",
                "note": "Close-to-close event window; not a causal proof.",
            }
        )

    catalysts = [
        {"date_or_window": "2026", "category": "Policy", "item": "45X advanced manufacturing production credit", "status": "Active but politically sensitive", "why_it_matters": "Q1 2026 gross margin includes large 45X benefit; FY2026 guide embeds about $2.145bn 45X credit.", "monitor": "IRS/Treasury guidance, OBBBA transition rules, company disclosure of credit recognition/cash tax.", "risk_level": "High", "source_id": "S3;S6;S7"},
        {"date_or_window": "2026 H2", "category": "Trade", "item": "Section 232 polysilicon/derivatives and related tariff actions", "status": "Open policy path", "why_it_matters": "Could widen price umbrella for U.S.-made modules, but can also raise input/project costs.", "monitor": "BIS/Commerce determinations, tariff rate, exemptions and effective dates.", "risk_level": "High", "source_id": "S9"},
        {"date_or_window": "2026", "category": "Trade/IP", "item": "TOPCon Section 337 / patent-import disputes", "status": "Investigative docket", "why_it_matters": "Could pressure imported crystalline competitors and improve FSLR relative positioning; legal outcomes are uncertain.", "monitor": "USITC procedural schedule, initial determination, settlement/licensing.", "risk_level": "Medium", "source_id": "S10"},
        {"date_or_window": "2026-2027", "category": "Demand", "item": "U.S. utility-scale solar and data-center power demand", "status": "Core demand driver", "why_it_matters": "Backlog is strong but incremental bookings and ASP decide whether 2027-2029 revenue bridge is credible.", "monitor": "New contracts GW, backlog ASP, cancellation/termination disclosures, interconnection delays.", "risk_level": "High", "source_id": "S1;S3;S4"},
        {"date_or_window": "2026-2028", "category": "Execution", "item": "Alabama/Louisiana/India capacity ramp and CuRe transition", "status": "Execution in progress", "why_it_matters": "FSLR's premium multiple requires clean execution, higher efficiency and unit-cost progress.", "monitor": "Production GW, throughput, warranty claims, capex, module efficiency roadmap.", "risk_level": "Medium", "source_id": "S2;S3;S4"},
        {"date_or_window": "2026-2029", "category": "Execution / Demand", "item": "Backlog conversion and ASP durability", "status": "Core valuation driver", "why_it_matters": "Large backlog supports revenue visibility, but cancellations, delivery delays and lower new ASPs could weaken the 2027-2029 revenue bridge.", "monitor": "Net bookings GW, backlog ASP, cancellations, delivery schedule, customer concentration.", "risk_level": "High", "source_id": "S1;S3;S4"},
        {"date_or_window": "Ongoing", "category": "Balance sheet", "item": "$1.5bn revolver and net cash", "status": "Strong liquidity", "why_it_matters": "Net cash reduces downside and funds capacity; working capital swings can still move quarterly FCF.", "monitor": "Net cash, revolver draw, operating cash flow and capex.", "risk_level": "Low/Medium", "source_id": "S1;S2;S13"},
    ]

    research_path = [
        {"key_question": "Is FSLR fairly valued, overvalued, or still underappreciated given 2026 EBITDA power and policy-adjusted risk?", "why_it_matters": "当前估值已不便宜，但公司质量、45X、backlog 和净现金使 $290-$310 区间的风险收益仍偏正。", "data_to_track": "FY2026 EBITDA run-rate, EV/FY2026 EBITDA, TTM P/E, net cash, policy-adjusted multiple.", "threshold_or_signpost": "$290-$310 主动建仓；$260-$280 且 thesis intact 加仓；$360-$380 无经营上修则减仓；跌破 $250-$255 且出现 thesis break 则认错。", "current_read": f"At ~{key_metrics['ev_ebitda_fy2026_mid']:.1f}x FY2026 EBITDA and ~{key_metrics['pe_ttm_company_basis']:.1f}x TTM P/E, FSLR is not deep value, but current-price risk/reward supports active building with explicit stop/reassessment triggers.", "source_id": "S1;S3;S11;S12"},
        {"key_question": "backlog 是护城河还是峰值订单？", "why_it_matters": "47.9GW/$14.4bn 说明可见度强，但股票看的是新增订单价格、取消风险和交付质量。", "data_to_track": "Net bookings GW, new bookings ASP, backlog value, backlog ASP, cancellations, delivery years.", "threshold_or_signpost": "新增 bookings ASP 接近或高于 $0.30/W，且 2027-2029 交付不断档。", "current_read": "Q1 后 backlog ASP 约 $0.30/W；YTD bookings 3.7GW；下一步必须验证新增订单 ASP。", "source_id": "S1;S3"},
        {"key_question": "45X 是否是可持续 earnings，还是会被折价？", "why_it_matters": "45X 是 margin 和现金流的重要变量，政策折现率决定估值倍数。", "data_to_track": "45X recognized in gross profit, cash realization, tax-line treatment, IRS/Treasury rules, PFE/FEOC restrictions.", "threshold_or_signpost": "规则稳定且公司披露现金化路径清晰，可降低市场折价。", "current_read": "FY2026 guide embeds about $2.145bn 45X credit；必须单独验证 cash realization，不能只看 EBITDA。", "source_id": "S3;S6;S7"},
        {"key_question": "贸易保护是增量利好还是需求破坏？", "why_it_matters": "关税/IP 限制能提高进口对手成本，但过高组件价格也会压制项目经济性。", "data_to_track": "Commerce/BIS/USITC actions, U.S. module prices, PPA economics, utility procurement.", "threshold_or_signpost": "国内供应溢价上升但项目未明显推迟，是最优组合。", "current_read": "AD/CVD、232、TOPCon 都是偏事件驱动变量。", "source_id": "S8;S9;S10;S14"},
        {"key_question": "产能扩张能否兑现成自由现金流？", "why_it_matters": "增长股要从 capex 周期切到 FCF 周期才更容易重估。", "data_to_track": "Production GW, sold GW, capex, OCF, inventory, warranty, efficiency, OCF-capex conversion.", "threshold_or_signpost": "OCF > capex 的季度持续出现，同时产能利用率上行。", "current_read": "2025 OCF $2.06bn，capex $0.87bn；Q1 2026 OCF -$214.9mn，需跟踪 Q2/Q3 是否恢复。", "source_id": "S2;S3;S4"},
    ]

    action_framework = [
        {"action": "主动建仓", "price_zone": "$290-$310", "position_action": "建立 40%-60% 目标仓位", "operating_triggers": "无 45X、backlog、OCF 或 FY2026 guide 的 thesis break", "risk_control": "不是一把梭；后续用经营触发器决定补仓或减仓", "source_id": "S1;S3;S11;S12"},
        {"action": "回撤加仓", "price_zone": "$260-$280", "position_action": "补到 70%-90% 目标仓位", "operating_triggers": "backlog ASP 稳定、无重大取消/延迟，45X 现金化路径未恶化", "risk_control": "若回撤来自政策或订单实质恶化，不加仓", "source_id": "S1;S3;S6;S7"},
        {"action": "确认加仓", "price_zone": "$310-$330", "position_action": "最多补到满仓", "operating_triggers": "新增 bookings ASP 接近/高于 $0.30/W；45X cash realization 清晰；OCF-capex 转正；2027-2029 收入桥更清楚，至少满足两项", "risk_control": "只为经营确认加仓，不为单日政策新闻追价", "source_id": "S1;S3;S6;S7;S8;S9"},
        {"action": "持有观察", "price_zone": "$330-$360", "position_action": "持有，不主动扩仓", "operating_triggers": "FY2026 EBITDA run-rate、毛利率和 backlog conversion 与模型一致", "risk_control": "若估值先涨而经营未上修，准备减仓", "source_id": "S1;S3;S12"},
        {"action": "减仓", "price_zone": "$360-$380", "position_action": "降低 20%-40% 仓位", "operating_triggers": "股价接近 bull case，但没有 EBITDA、backlog ASP 或 45X 确定性上修；或 EV/FY2026 EBITDA 高于约 13x", "risk_control": "保留核心仓位等待下一轮数据，不把 bull case 当 base case", "source_id": "S1;S3;S12"},
        {"action": "认错/止损", "price_zone": "<$250-$255 或经营触发器失效", "position_action": "减至小仓或退出并重做模型", "operating_triggers": "FY2026 EBITDA run-rate/guide 低于约 $2.5bn；新增 bookings ASP < $0.27/W；重大取消/延迟；45X 现金化受阻；OCF-capex 连续两个季度不恢复；2027-2029 收入桥断档", "risk_control": "价格跌破区间必须结合 thesis break；经营触发器失效时不等价格确认", "source_id": "S1;S3;S6;S7;S11;S12"},
    ]

    write_csv("sources.csv", sources)
    write_csv("financials_kpis.csv", financials)
    write_csv("valuation_peers.csv", peers)
    write_csv("market_reaction.csv", reactions)
    write_csv("catalysts_policy_risks.csv", catalysts)
    write_csv("research_path.csv", research_path)
    write_csv("investment_action_framework.csv", action_framework)
    write_csv("market_price_history_fslr_tan.csv", history_fslr + history_tan)
    write_json("research_data.json", {
        "run_date": RUN_DATE,
        "company": {"name": "First Solar, Inc.", "ticker": "FSLR", "exchange": "NASDAQ"},
        "key_metrics": key_metrics,
        "financials_kpis": financials,
        "valuation_peers": peers,
        "valuation_scenarios": scenarios,
        "market_reaction": reactions,
        "catalysts_policy_risks": catalysts,
        "research_path": research_path,
        "investment_action_framework": action_framework,
        "sources": sources,
    })

    readme = f"""# First Solar (FSLR) 中文深度研究

这是一个独立研究项目，目标不是新闻摘要，而是可审阅、可复用、可发布的 First Solar（NASDAQ: FSLR）投资研究底稿。

## Thesis

FSLR 不是传统“太阳能 beta”交易。它更像一个美国工业政策、贸易保护和稀缺本土产能共同支撑的高波动制造业资产。公司基本面强，backlog 可见度高，资产负债表干净；当前股价不算便宜，但 $290-$310 区间的风险收益仍支持偏买/主动建仓，后续用价格带和经营触发器加减仓。

## 关键结论

- Q1 2026 net sales 为 $1.044bn，调整后 EBITDA 为 $520mn，EPS 为 $3.22；全年指引维持在 net sales $4.9-$5.2bn、调整后 EBITDA $2.6-$2.8bn。
- Q1 末已签约 backlog 为 47.9GW、$14.4bn，隐含约 $0.30/W。backlog 是核心护城河，但未来股价更看新增 bookings 的价格和交付年份。
- 按当前价格约 ${key_metrics['current_price_usd']:.2f}、Q1 diluted shares 107.6mn 和净现金约 $2.0bn 估算，EV/FY2026 EBITDA midpoint 约 {key_metrics['ev_ebitda_fy2026_mid']:.1f}x，已经接近基本情景。
- 投资框架偏“主动建仓”：$290-$310 建立 40%-60% 目标仓位；$260-$280 且 thesis intact 加仓；$360-$380 若无经营上修则减仓；跌破 $250-$255 且出现 45X/backlog/OCF thesis break 则认错。

## 项目结构

- `investment_memo.md`：中文投资备忘录
- `publish_long_post_zh.md`：可直接发布的中文长帖
- `data/`：整理后的 CSV/JSON 数据表，均带 source_id
- `outputs/first_solar_fslr_research_workbook.xlsx`：Excel workbook；若该文件正在桌面 Excel 中打开，脚本会另存为 `_updated.xlsx` 或 timestamp 版本
- `media/`：中文媒体 PNG 图；`tweet_*.png` 为新版长帖对应推文图
- `scripts/`：重建数据、图片和 workbook 的脚本

## 如何重建

1. 运行 `scripts/build_research_assets.py` 生成数据表、memo、长帖和 PNG。
2. 运行 `scripts/build_workbook.mjs` 生成 Excel workbook。
3. 数据源索引见 `data/sources.csv`；核心模型数据见 `data/research_data.json`。

本项目数据截至 {RUN_DATE}。市场价格和估值会随交易日变化，复用时请先重跑脚本并重新检查 `Checks` sheet。
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")

    memo = f"""# First Solar（FSLR）投资备忘录

数据截至：{RUN_DATE}

## 结论先行

FSLR 的核心矛盾不是“太阳能行业景气度是否好”，而是美国本土薄膜组件产能能不能在政策保护期内，把 45X、贸易壁垒和数据中心/公用事业需求转成可持续现金流。公司当前基本面很强：Q1 2026 收入 $1.044bn、毛利率 46.6%、调整后 EBITDA $520mn、净现金约 $2.0bn，backlog 47.9GW/$14.4bn。按公司口径估算 EV/FY2026 EBITDA midpoint 约 {key_metrics['ev_ebitda_fy2026_mid']:.1f}x，base case 并不显示明显低估，但质量、净现金和政策/订单可见度使当前价格附近仍是偏买/主动建仓。

投资方向上，我更偏向“当前价格附近主动建仓”。这不是一个低估值捡烟蒂，也不是便宜到不用思考；它是政策、订单、产能执行共同驱动的质量制造股。$290-$310 建 40%-60% 目标仓位，$260-$280 且 thesis intact 再加，$360-$380 如果没有经营上修就减。错了也有清楚的认错线：跌破 $250-$255 且出现 45X、backlog、OCF 或 FY2026 guide 的实质恶化，就减到小仓或退出重做模型。

## 最关键的问题

第一，backlog 是否还能高质量续上。Q1 末 backlog 为 47.9GW、$14.4bn，隐含约 $0.30/W。这个数字给了未来收入可见度，但股票不会因为“已有订单多”无限上涨。真正要看的是新增 bookings 的价格、交付年份、客户集中度和取消条款。

第二，45X 的利润到底该给多少倍数。公司 2026 指引里嵌入约 $2.145bn 的 45X benefit。它是真金白银式的制造税收抵免，但政策敏感度高。若 IRS/Treasury 和 OBBBA 后续规则保持稳定，市场会降低折价；若 FEOC/PFE 或 credit monetization 变复杂，估值倍数要打折。

第三，贸易保护是利润保护还是需求破坏。AD/CVD、Section 232、TOPCon/USITC 等事件能扩大 FSLR 的相对优势，也可能提高项目成本并推迟需求。最好的组合是进口竞争成本上升，而美国 utility-scale 项目经济性没有被明显破坏。

## 事实底稿

2025 年公司收入 $5.219bn、净利润 $1.528bn、EPS $14.21、经营现金流 $2.057bn、capex $870mn。Q1 2026 收入同比增长约 24%，EPS 从 $1.95 提升到 $3.22，调整后 EBITDA margin 接近 50%。资产负债表更关键：Q1 末现金及可交易证券约 $2.427bn，债务约 $426mn，净现金约 $2.001bn。

业务 KPI 上，2025 年 module sold 为 16.7GW；Q1 2026 sold 3.8GW，produced 4.3GW。公司全年指引中 sold volume midpoint 为 17.6GW，说明 2026 不只是出货增长，更重要的是价格、margin、45X 和交付节奏。

## 估值

按当前价格约 ${key_metrics['current_price_usd']:.2f}、Q1 diluted shares 107.6mn、净现金约 $2.0bn 粗算，市值约 ${key_metrics['market_cap_usd_bn_company_basis']:.1f}bn，EV 约 ${key_metrics['ev_usd_bn_company_basis']:.1f}bn。对应 TTM EPS 约 ${key_metrics['ttm_eps_usd']:.2f}，P/E 约 {key_metrics['pe_ttm_company_basis']:.1f}x；对应 FY2026 adjusted EBITDA midpoint $2.7bn，EV/EBITDA 约 {key_metrics['ev_ebitda_fy2026_mid']:.1f}x。

情景上，熊市情景用 $2.3bn EBITDA 和 8x EV/EBITDA，隐含股价约 ${scenarios[0]['implied_price_usd']:.0f}；基本情景用 $2.7bn 和 10x，约 ${scenarios[1]['implied_price_usd']:.0f}；牛市情景用 $3.2bn 和 12x，约 ${scenarios[2]['implied_price_usd']:.0f}。当前价格已经高于 base case，说明市场已经反映一部分 45X 和 backlog 可见度。这不妨碍偏买判断，但仓位必须跟着证据走：若新增订单 ASP、backlog 兑现、毛利率和政策确定性继续支持，公司可以向 bull case 靠近；若这些变量反向变化，就不能把 bull case 当 base case。

## 市场反应

事件窗口显示，市场对 earnings、政策和贸易事件反应很快，但方向并不等同于长期基本面。例如 Q1 2026 earnings 后的 close-to-close 反应为 {next(r['fslr_return_pct'] for r in reactions if r['event_date']=='2026-04-30'):.1f}%，相对 TAN alpha 为 {next(r['alpha_vs_tan_pct'] for r in reactions if r['event_date']=='2026-04-30'):.1f}pct。这个反应说明预期已经不低，后续更要看订单和政策落地。

## 政策与监管

FSLR 是政策敏感行业中的政策受益者，但受益者也要承担政策折现。45X 是利润表和现金流的核心变量；AD/CVD 和 Section 232 影响进口竞争和价格 umbrella；TOPCon/USITC 影响晶硅竞争格局；OBBBA 之后的 clean-energy credit、FEOC/PFE 规则影响客户项目经济性和融资。

## 投资框架

我的框架是：不把它当普通太阳能股，也不把它当无风险政策套利。FSLR 不是纯粹低估标的，而是高质量但政策敏感的 earnings compounder。当前价格附近偏买/主动建仓，$290-$310 建 40%-60% 目标仓位；$260-$280 且 backlog ASP、45X 和 OCF 没有恶化时加仓；$310-$330 只有在新增 bookings ASP、45X cash realization、OCF-capex、2027-2029 收入桥至少两项确认时再加；$360-$380 若没有 EBITDA、backlog ASP 或政策确定性上修，则降低 20%-40% 仓位。

认错条件也要硬：若股价跌破 $250-$255 且出现 thesis break，或不等价格但经营数据先坏掉，就减到小仓或退出。具体看 FY2026 EBITDA run-rate/guide 是否低于约 $2.5bn，新增 bookings ASP 是否跌破 $0.27/W，backlog 是否出现重大取消/延迟，45X 现金化是否受阻，OCF-capex 是否连续两个季度不恢复，以及 2027-2029 收入桥是否断档。

需要继续跟踪的指标是：新增 bookings GW 和 ASP、backlog delivery year、cancellations、45X cash realization、FY2026 EBITDA run-rate、Section 232/AD-CVD/TOPCon 进展、OCF-capex、产能利用率和 warranty/quality disclosure。

## 来源

所有表格来源映射见 `data/sources.csv`。核心数据来自 SEC filings、公司 earnings release/presentation、IRS、Commerce、BIS、USITC、Yahoo Finance 和 StockAnalysis。
"""
    (ROOT / "investment_memo.md").write_text(memo, encoding="utf-8")

    post = f"""FSLR（First Solar）我现在的看法是：当前价格附近偏买，适合主动建仓，但必须带价格带和经营触发器。

它不是普通“太阳能板块反弹”逻辑。FSLR 的核心价值在于美国本土、非晶硅路线、规模化薄膜组件产能。简单说，它卖的不是一个光伏组件 beta，而是美国公用事业级太阳能供应链里少见的“确定性产能 + 政策信用 + 已签订单”。

为什么看好？

第一，需求端不是住宅太阳能那套高利率压力逻辑，而是 utility-scale、电网建设、数据中心用电和大型企业购电。美国未来几年电力需求往上走，太阳能仍然是最容易快速部署的新增电源之一。

第二，供给端稀缺。FSLR 的 CdTe 薄膜路线不依赖传统晶硅/多晶硅链条，产能主要在美国和友好地区。这个差异在正常周期里只是技术差异，在贸易保护和供应链安全周期里会变成估值差异。

第三，公司已经有很高可见度。Q1 2026 末 contracted backlog 47.9GW、价值 $14.4bn，隐含约 $0.30/W。这个 backlog 不是当前收入，但它说明未来几年收入桥不是空中楼阁。

第四，资产负债表干净。Q1 末净现金约 $2.0bn。制造业扩产最怕高杠杆和现金流断裂，FSLR 目前这点比多数太阳能链公司舒服。

为什么不是观望？

因为研究不能只说“等验证”。用当前股价约 ${key_metrics['current_price_usd']:.2f}、Q1 diluted shares 107.6mn、净现金约 $2.0bn 粗算，公司口径 EV 约 ${key_metrics['ev_usd_bn_company_basis']:.1f}bn。对 FY2026 adjusted EBITDA midpoint $2.7bn，是大约 {key_metrics['ev_ebitda_fy2026_mid']:.1f}x EV/EBITDA。base case implied price 低于当前股价，说明它不是明显低估；但质量、净现金、backlog 和政策可见度让 $290-$310 区间可以主动建仓，而不是把判断推给未来。

模型里最关键的数字逻辑有三层。第一，收入并没有爆发式增长：2023A net sales $3.319bn，2024A $4.206bn，2025A $5.219bn，但 FY2026 guidance midpoint 是 $5.050bn，反而略低于 2025A。第二，利润更强来自 gross profit 和 gross margin：2026E gross profit midpoint $2.5bn，gross margin 49.5%，高于 2025A 的 40.6%。这说明估值不是单纯买 revenue growth，而是在买 margin expansion，尤其是 45X credit。第三，backlog 给长期收入 visibility：47.9GW / $14.4bn、backlog ASP 约 $0.3006/W，说明订单不只是量大，也有相对高价合约保护。

更重要的是，FSLR 的利润里有很强的政策变量。公司 2026 指引里嵌了约 $2.145bn 的 45X benefit。45X 是真实收益，但市场会问：这个收益能持续多久？规则会不会收紧？能不能顺利现金化？所以它不能简单按普通经营利润给满倍数。

还有一点，backlog 很大，但股价看的是增量。下一步最关键不是重复说 47.9GW backlog，而是看新增 bookings 的 ASP、交付年份、客户质量和取消风险。如果新订单价格开始走弱，backlog 的“护城河”就会被市场重新定价。

所以我的结论是：趋势偏正面，当前价格附近偏买。若 45X 规则稳定、Section 232/AD-CVD/TOPCon 继续抬高进口竞争成本，同时新增订单 ASP 稳住，FSLR 有机会从基本情景往牛市情景走。反过来，如果政策折现变大、项目成本伤害需求，或者 2027-2029 新单接不上，就要按纪律减仓，不把“好公司”当成忽略风险的理由。

Peers 表里放了 ENPH/SEDG 这类逆变器和储能，CSIQ/JKS 这类全球组件，ARRY/SHLS/NXT 这类 tracker 和 EBOS，还有 RUN 这种住宅太阳能服务。这组对比只能做 solar ecosystem 的方向性参考，不能用同一个 multiple 直接套 FSLR。FSLR 明显比商品化组件厂贵，但它有 CdTe 技术路线、美国制造 footprint、净现金、backlog 可见度和 45X 敏感度，所以应该单独处理；问题是这个溢价现在已经不小，后面必须靠订单和政策继续兑现。

policy risk 表则是这份研究最重要的跟踪页之一。FSLR 的政策不是单边利好，而是“护城河 + 风险折现”一起存在。45X 决定利润质量；OBBBA、FEOC/PFE 影响客户项目能否拿 credit；AD/CVD 和 Section 232 影响进口竞争和价格 umbrella；TOPCon/USITC 影响晶硅竞争格局。这些变量任何一个变化，都可能比季度收入多一点少一点更影响估值。

我的操作框架很简单：$290-$310 先建 40%-60% 目标仓位；$260-$280 且 backlog ASP、45X、OCF 没有恶化时加仓；$310-$330 只有在新增 bookings ASP 接近/高于 $0.30/W、45X cash realization 清晰、OCF-capex 转正、2027-2029 收入桥更清楚这些条件里至少两项成立时再加；$360-$380 如果没有 EBITDA、backlog ASP 或政策确定性上修，减掉 20%-40%。

认错条件也写清楚：跌破 $250-$255 且出现 thesis break，就减到小仓或退出重做模型。经营触发器比价格更重要，FY2026 EBITDA run-rate/guide 低于约 $2.5bn、新增 bookings ASP 低于 $0.27/W、backlog 出现重大取消/延迟、45X 现金化受阻、OCF-capex 连续两个季度不恢复，任何一个变成主线，都要改判断。

一句话：FSLR 不是纯粹低估标的，但当前价格附近偏买。核心价值是美国本土 CdTe 产能、政策信用、净现金和高价 backlog；未来趋势取决于新增 bookings ASP、backlog conversion、45X cash realization、OCF-capex 和贸易政策落地。
"""
    (ROOT / "publish_long_post_zh.md").write_text(post, encoding="utf-8")

    save_card(
        "01_core_thesis.png",
        "FSLR：美国太阳能制造的稀缺资产",
        "不是普通太阳能 beta，而是政策、贸易保护、backlog 和执行力共同定价",
        [
            "Q1 2026：收入 $1.044bn，调整后 EBITDA $520mn，EPS $3.22",
            "backlog 47.9GW / $14.4bn，隐含约 $0.30/W",
            f"当前约 {key_metrics['ev_ebitda_fy2026_mid']:.1f}x EV/FY2026 EBITDA midpoint，接近基本情景",
            "投资方向：$290-$310 偏买/主动建仓；用价格带和经营触发器控风险",
        ],
        font_path,
        "#0E7C66",
    )

    save_card(
        "02_financials_valuation.png",
        "财务强，但市场已重估",
        "利润质量高，净现金强；下一段回报要靠 2027 之后的订单和政策兑现",
        [
            "Q1 2026 毛利率 46.6%，调整后 EBITDA margin 49.8%",
            "2025 OCF $2.06bn，capex $0.87bn；Q1 2026 OCF 仍受营运资本影响",
            f"TTM EPS 约 ${key_metrics['ttm_eps_usd']:.2f}，公司口径 P/E 约 {key_metrics['pe_ttm_company_basis']:.1f}x",
            f"净现金约 $2.0bn，资产负债表给了下行缓冲",
        ],
        font_path,
        "#365F91",
    )

    save_bar_card(
        "03_market_reaction.png",
        "市场反应：政策和财报都能快速重定价",
        "下面是 FSLR 相对 TAN 的事件窗口 alpha",
        [r["event_date"][5:] for r in reactions],
        [r["alpha_vs_tan_pct"] for r in reactions],
        "pct",
        font_path,
        "#0E7C66",
    )

    save_card(
        "04_policy_risks.png",
        "政策是护城河，也是估值折现项",
        "FSLR 的优势来自规则，但规则本身必须持续跟踪",
        [
            "45X：FY2026 guide embeds about $2.145bn benefit，决定 margin 和现金流质量",
            "AD/CVD + Section 232：提高进口竞争成本，也可能影响项目经济性",
            "TOPCon/USITC：若进口晶硅受限，FSLR 相对位置更强，但法律结果不确定",
            "OBBBA / FEOC / PFE：客户项目能否拿到 credit，影响真实需求",
        ],
        font_path,
        "#8A5B20",
    )

    scenario_labels = [s["scenario"] for s in scenarios]
    scenario_values = [s["implied_price_usd"] for s in scenarios]
    save_bar_card(
        "05_investment_framework.png",
        "投资框架：主动建仓，但有纪律",
        "$290-$310 偏买；$260-$280 加仓；$360-$380 减仓；<$250-$255 且 thesis break 认错",
        scenario_labels,
        scenario_values,
        "$",
        font_path,
        "#365F91",
    )

    current_vs_base = scenarios[1]["implied_price_usd"] / key_metrics["current_price_usd"] - 1
    save_tweet_card(
        "tweet_01_conclusion.png",
        "FSLR：当前偏买 / 主动建仓",
        "不是深度低估，但 $290-$310 区间的风险收益支持先建仓。",
        [
            ("核心价值", "美国本土 CdTe 薄膜组件产能，叠加政策信用、净现金和已签 backlog。"),
            ("动作", "$290-$310 建 40%-60% 目标仓位；不是一把梭。"),
            ("加仓", "$260-$280 thesis intact；或新增 ASP、45X、OCF、收入桥至少两项确认。"),
            ("认错", "<$250-$255 且 thesis break；经营触发器失效时不等价格确认。"),
        ],
        font_path,
        "#0E7C66",
    )

    save_tweet_card(
        "tweet_02_numbers_logic.png",
        "数字逻辑：买的不是收入爆发",
        "2026 指引显示，收入不是主要亮点，margin 和 backlog 才是估值核心。",
        [
            ("收入没有爆发", "Net sales：2023A $3.319bn，2024A $4.206bn，2025A $5.219bn；2026E midpoint $5.050bn。"),
            ("利润更强", "2026E gross profit midpoint $2.5bn，gross margin 49.5%，高于 2025A 的 40.6%。"),
            ("45X 是核心变量", "2026 指引嵌入约 $2.145bn 45X benefit；估值不能只看 EBITDA，要看 cash realization。"),
            ("backlog 给可见度", "47.9GW / $14.4bn，backlog ASP 约 $0.3006/W；下一步看新增 ASP 和取消风险。"),
        ],
        font_path,
        "#365F91",
    )

    save_tweet_valuation_card(
        "tweet_03_valuation_scenarios.png",
        key_metrics["current_price_usd"],
        scenarios,
        font_path,
    )

    save_tweet_card(
        "tweet_04_peers_context.png",
        "Peers：FSLR 要单独处理",
        "同行表是 solar ecosystem 的方向性对比，不能把同一个 multiple 直接套到 FSLR。",
        [
            ("组件厂对比", "CSIQ/JKS 更接近全球商品化组件；FSLR 因美国制造和 CdTe 路线应有溢价。"),
            ("设备链对比", "ENPH/SEDG、ARRY/SHLS/NXT 分别是逆变器、tracker、EBOS，商业模式和 margin 不同。"),
            ("公司口径 EV", f"FSLR peers 行已统一为公司口径 EV 约 ${key_metrics['ev_usd_bn_company_basis']:.1f}bn。"),
            ("结论", "FSLR 的溢价有理由；当前偏买，但高位继续加仓要看订单和政策兑现。"),
        ],
        font_path,
        "#6E5AA8",
    )

    save_tweet_card(
        "tweet_05_policy_risk.png",
        "Policy Risk：护城河 + 风险折现",
        "FSLR 是政策受益者，但政策收益不能当作无风险普通利润。",
        [
            ("45X", "决定 gross margin 和现金流质量；重点看 credit recognition、cash realization 和税务口径。"),
            ("OBBBA / FEOC / PFE", "影响客户项目能否拿 credit，进而影响真实需求和融资。"),
            ("AD/CVD / Section 232", "提高进口竞争成本，也可能推高项目成本、拖累需求。"),
            ("Backlog conversion", "新增 risk：取消、延迟、ASP 下滑都会削弱 2027-2029 收入桥。"),
        ],
        font_path,
        "#8A5B20",
    )

    save_tweet_card(
        "tweet_06_monitoring_checklist.png",
        "建仓纪律：价格带 + 经营触发器",
        "结论是偏买，但仓位不能脱离数据。",
        [
            ("建仓", "$290-$310 建 40%-60% 目标仓位。"),
            ("加仓", "$260-$280 thesis intact；$310-$330 只为经营确认加。"),
            ("减仓", "$360-$380 且无 EBITDA/backlog ASP/政策上修，减 20%-40%。"),
            ("认错", "<$250-$255 + thesis break；ASP<$0.27/W、45X受阻、OCF-capex连续不恢复即改判断。"),
        ],
        font_path,
        "#10231F",
    )


if __name__ == "__main__":
    main()
