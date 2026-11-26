import json, re, os
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

URL = "https://new2.moci.gov.kw/ar/gold/"
OUT = "data/prices.json"
TZ = ZoneInfo("Asia/Kuwait")

def norm(s):
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789..")).replace(",", "").strip()

def main():
    response = requests.get(URL, timeout=30, headers={"User-Agent":"Mozilla/5.0 KuwaitGoldIndex/1.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = " ".join(soup.stripped_strings)
    # Parse the official table by row labels, not by inferred market prices.
    prices = {}
    ounce = None
    rows = soup.find_all("tr")
    for tr in rows:
        cells = [norm(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        label = cells[0]
        match = re.search(r"(?:عيار\s*)?(24|22|21|18)", label)
        if match and "عيار" in label:
            nums = re.findall(r"\d+(?:\.\d+)?", " ".join(cells[1:]))
            if nums: prices[match.group(1)] = float(nums[0])
        elif "الأونصة" in label or "الاونصة" in label:
            nums = re.findall(r"\d+(?:\.\d+)?", " ".join(cells[1:]))
            if nums: ounce = float(nums[0])
    if set(prices) != {"24","22","21","18"} or ounce is None:
        raise RuntimeError("تعذر استخراج جميع أسعار العيارات والأونصة من جدول الوزارة؛ لم يتم حفظ قراءة ناقصة.")
    stamp = datetime.now(TZ)
    update_match = re.search(r"آخر تحديث\s*[:：]?\s*(.{5,60}?)(?:\s+(?:النوع|عيار\s*24)|$)", text)
    source_update = update_match.group(1).strip() if update_match else ""
    record = {"date": stamp.strftime("%Y-%m-%d"), "time": stamp.strftime("%H:%M"), "updated_at": stamp.strftime("%Y-%m-%d %H:%M"), "source_updated_at": source_update, "prices": prices, "ounce": ounce, "source": URL}
    os.makedirs("data", exist_ok=True)
    data = {"source": URL, "currency": "KWD", "unit": "gram", "history": []}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f: data = json.load(f)
    history = data.get("history", [])
    # One daily entry: if the workflow is manually re-run, keep that day's latest official reading.
    history = [x for x in history if x.get("date") != record["date"]]
    history.append(record)
    history.sort(key=lambda x: x["date"])
    data.update({"source": URL, "currency": "KWD", "unit": "gram", "history": history, "last_updated": record["updated_at"]})
    with open(OUT, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    print("Saved official reading:", record["updated_at"], prices, "ounce:", ounce)

if __name__ == "__main__":
    main()
