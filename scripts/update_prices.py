import json, re, os
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

URL = "https://api.moci.gov.kw/ar/market-prices/gold/"
OUT = "data/prices.json"
TZ = ZoneInfo("Asia/Kuwait")

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789..")

def norm(s):
    return s.translate(DIGITS).replace(",", "").strip()

def first_number(value):
    match = re.search(r"\d+(?:\.\d+)?", norm(value))
    return float(match.group()) if match else None

def main():
    response = requests.get(URL, timeout=30, headers={"User-Agent":"Mozilla/5.0 KuwaitGoldIndex/1.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = norm(" ".join(soup.stripped_strings))

    # First try semantic table rows.
    prices = {}
    ounce = None
    for tr in soup.find_all("tr"):
        cells = [norm(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        label = cells[0]
        match = re.search(r"(?:عيار\s*)?(24|22|21|18)", label)
        if match and "عيار" in label:
            value = first_number(" ".join(cells[1:]))
            if value is not None:
                prices[match.group(1)] = value
        elif "الأونصة" in label or "الاونصة" in label:
            ounce = first_number(" ".join(cells[1:]))

    # Fallback for the ministry page when its visible data is rendered in non-table elements.
    if set(prices) != {"24", "22", "21", "18"} or ounce is None:
        for karat in ("24", "22", "21", "18"):
            match = re.search(r"عيار\s*" + karat + r"\s*[:：\-]?\s*(\d+(?:\.\d+)?)", text)
            if match:
                prices[karat] = float(match.group(1))
        ounce_match = re.search(r"(?:الأونصة|الاونصة)\s*[:：\-]?\s*(\d+(?:\.\d+)?)", text)
        if ounce_match:
            ounce = float(ounce_match.group(1))

    if set(prices) != {"24", "22", "21", "18"} or ounce is None:
        preview = text[:1200]
        raise RuntimeError(
            "تعذر استخراج جميع الأسعار من صفحة الوزارة. لم يتم حفظ قراءة ناقصة. "
            "مقتطف الصفحة للتشخيص: " + preview
        )

    stamp = datetime.now(TZ)
    update_match = re.search(r"آخر تحديث\s*[:：]?\s*(.{5,60}?)(?:\s+(?:النوع|عيار\s*24)|$)", text)
    source_update = update_match.group(1).strip() if update_match else ""
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

    history = data.get("history", [])
    history = [x for x in history if x.get("date") != record["date"]]
    history.append(record)
    history.sort(key=lambda x: x["date"])
    data.update({
        "source": URL,
        "currency": "KWD",
        "unit": "gram",
        "history": history,
        "last_updated": record["updated_at"]
    })
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Saved official reading:", record["updated_at"], prices, "ounce:", ounce)

if __name__ == "__main__":
    main()
