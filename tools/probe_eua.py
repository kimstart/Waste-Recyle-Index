# -*- coding: utf-8 -*-
"""EUA 가격 후보 점검: Yahoo 심볼들, EEX 경매 결과 웹서비스"""
import sys, os, re, json, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get
from collect_biogas import yahoo_series
for sym in ("CO2.L", "CO2.DE", "CO2.AS", "KEUA", "EUA=F", "CFI2Z6.NYM", "CKZ26.NYM", "MOZ26.NYM", "ECF=F", "C=F"):
    try:
        s = yahoo_series(sym)
        print(f"{sym}: {len(s)}개, 최근 {s[-3:]}")
    except Exception as e:
        print(f"{sym}: 실패 {type(e).__name__} {str(e)[:60]}")
# EEX 경매 결과: 페이지 JS에서 쓰는 웹서비스 경로 찾기
h = get("https://www.eex.com/en/market-data/environmentals/eu-ets-auctions")
js = re.findall(r'<script[^>]+src="([^"]+)"', h)
print("js:", [j for j in js if "eex" in j or j.startswith("/")][:15])
for j in js:
    if not (j.startswith("/") or "eex.com" in j): continue
    try:
        t = get(urllib.parse.urljoin("https://www.eex.com", j))
        hits = sorted(set(re.findall(r"https?://[A-Za-z0-9.-]+/[A-Za-z0-9/_.-]*(?:query|json|api)[A-Za-z0-9/_.-]*", t)))
        if hits: print("  ", j[-60:], hits[:8])
    except Exception:
        pass
