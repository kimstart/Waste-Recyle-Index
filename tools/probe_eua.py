# -*- coding: utf-8 -*-
import sys, os, re, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get
from collect_biogas import _xlsx_sheets
h = get("https://www.eex.com/en/market-data/environmentals/eu-ets-auctions")
print("api 후보:", sorted(set(re.findall(r"https?://[a-z0-9.-]*(?:gvsi|webservice|api)[a-z0-9./_-]*", h, re.I)))[:20])
print("fileadmin:", sorted(set(re.findall(r"/fileadmin/[^\"' ]+", h)))[:20])
for i in [m.start() for m in re.finditer(r"(?i)auction report|primary market auction", h)][:3]:
    print("ctx:", re.sub(r"\s+", " ", h[i - 300:i + 300]))
base = "https://www.eex.com/fileadmin/EEX/Downloads/EUA_Emission_Spot_Primary_Market_Auction_Report/"
for u in (base + "Archive_Reports/emission-spot-primary-market-auction-report-2026-data.xlsx",
          base + "emission-spot-primary-market-auction-report-2026-data.xlsx",
          base + "Archive_Reports/emission-spot-primary-market-auction-report-2025-data.xlsx"):
    try:
        b = get(u, raw=True)
        print("OK", u, len(b))
        sh = _xlsx_sheets(b)
        for name, rows in sh.items():
            print(f"  시트 {name}: {len(rows)}행")
            for r in rows[:7]: print("     ", dict(list(r.items())[:14]))
            for r in rows[-2:]: print("   …", dict(list(r.items())[:14]))
    except Exception as e:
        print("실패", u.split('/')[-1], type(e).__name__, str(e)[:80])
