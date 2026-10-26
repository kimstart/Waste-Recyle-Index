# -*- coding: utf-8 -*-
import sys, os, re, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get, retry
from collect_biogas import _xlsx_sheets
for page in ("https://www.eex.com/en/market-data/environmentals/eu-ets-auctions",
             "https://www.eex.com/en/markets/environmental-markets/eu-ets-auctions"):
    try:
        h = get(page)
        links = sorted(set(re.findall(r'href="([^"]+\.(?:xlsx|xls|csv))"', h, re.I)))
        print(f"== {page}: {len(h)}자, 파일 링크 {len(links)}")
        for l in links[:30]: print("   ", l)
    except Exception as e:
        print(page, "실패", type(e).__name__, str(e)[:100])
        links = []
    cand = [l for l in links if re.search(r"auction.*(report|result)|primary", l, re.I) and "2026" in l]
    if cand:
        u = urllib.parse.urljoin(page, cand[0])
        b = get(u, raw=True)
        sh = _xlsx_sheets(b)
        for name, rows in sh.items():
            print(f"  시트 {name}: {len(rows)}행")
            for r in rows[:8]: print("     ", dict(list(r.items())[:14]))
            for r in rows[-3:]: print("   …", dict(list(r.items())[:14]))
        break
