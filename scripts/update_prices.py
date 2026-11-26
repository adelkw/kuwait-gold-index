import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://new2.moci.gov.kw/ar/gold/"
OUT = "data/prices.json"
TZ = ZoneInfo("Asia/Kuwait")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789..")

def norm(value):
    return value.translate(DIGITS).replace(",", "").replace("٬", "").strip()

def extract_number(pattern, text):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(locale="ar-KW", timezone_id="Asia/Kuwait")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_function(
                "() => document.body && /عيار\s*24/.test(document.body.innerText) && /الأونصة|الاونصة/.test(document.body.innerText)",
                timeout=45000
            )
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(2500)
        body = page.locator("body").inner_text(timeout=15000)
        browser.close()

    text = norm(" ".join(body.split()))
    if "Javascript is required" in text or "You are being redirected" in text:
        raise RuntimeError("وزارة التجارة أعادت صفحة تحقق آلي ولم تسمح للمتصفح الآلي بالوصول إلى الأسعار.")

    prices = {}
    for karat in ("24", "22", "21", "18"):
        value = extract_number(r"عيار\s*" + karat + r"\s*(?:د\.?ك)?\s*([0-9]+(?:\.[0-9]+)?)", text)
        if value is None:
            value = extract_number(r"عيار\s*" + karat + r".{0,80}?([0-9]+(?:\.[0-9]+)?)", text)
        if value is not None:
            prices[karat] = value

    ounce = extract_number(r"(?:الأونصة|الاونصة)\s*(?:د\.?ك)?\s*([0-9]+(?:\.[0-9]+)?)", text)
    if ounce is None:
        ounce = extract_number(r"(?:الأونصة|الاونصة).{0,80}?([0-9]+(?:\.[0-9]+)?)", text)

    if set(prices) != {"24", "22", "21", "18"} or ounce is None:
        raise RuntimeError("لم يتم العثور على جميع الأسعار الرسمية بعد تشغيل JavaScript. مقتطف الصفحة: " + text[:1000])

    source_update_match = re.search(r"آخر تحديث\s*[:：]?\s*(.{5,70}?)(?:\s+(?:النوع|عيار\s*24)|$)", text)
    source_update = source_update_match.group(1).strip() if source_update_match else ""
    stamp = datetime.now(TZ)
    record = {
        "date": stamp.strftime("%Y-%m-%d"),
        "time": stamp.strftime("%H:%M"),
        "updated_at": stamp.strftime("%Y-%m-%d %H:%M"),
        "source_updated_at": source_update,
        "prices": prices,
        "ounce": ounce,
        "source": URL
    }

    os.makedirs("data", exist_ok=True)
    data = {"source": URL, "currency": "KWD", "unit": "gram", "history": []}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            data = json.load(f)

    history = [item for item in data.get("history", []) if item.get("date") != record["date"]]
    history.append(record)
    history.sort(key=lambda item: item["date"])
    data.update({
        "source": URL,
        "currency": "KWD",
        "unit": "gram",
        "history": history,
        "last_updated": record["updated_at"]
    })
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Saved ministry reading:", record["updated_at"], prices, "ounce:", ounce, "source update:", source_update)

if __name__ == "__main__":
    main()
