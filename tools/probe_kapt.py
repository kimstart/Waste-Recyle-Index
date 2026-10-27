# -*- coding: utf-8 -*-
"""K-APT 입찰결과 화면에서 엑셀 버튼이 어디에, 어떤 조건으로 보이는지 (화면 HTML 1회 조회)"""
import re, urllib.request
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import UA
h = urllib.request.urlopen(urllib.request.Request("https://www.k-apt.go.kr/bid/bidResultList.do", headers=UA), timeout=60).read().decode("utf8", "ignore")
sq = lambda t: re.sub(r"\s+", " ", t)
for kw in ("엑셀", "excel", "Excel", "다운로드"):
    for m in list(re.finditer(kw, h))[:6]:
        print(f"[{kw}]", sq(h[max(0, m.start() - 300):m.start() + 200]))
m = re.search(r"function\s+(\w+)\s*\([^)]*\)\s*\{[^{}]*?bidResultListExcel", h, re.S)
print("엑셀 함수:", m.group(1) if m else None)
