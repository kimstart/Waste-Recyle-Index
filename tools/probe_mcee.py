# -*- coding: utf-8 -*-
"""기후에너지환경부 게시판 구조 점검: 입법예고(68)·고시(71)가 0건으로 읽히는 원인"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get
for mid in (68, 71, 10557):
    for q in ("", "&pageIndex=2"):
        u = f"https://www.mcee.go.kr/home/web/index.do?menuId={mid}{q}"
        try:
            h = get(u, timeout=40)
        except Exception as e:
            print(mid, q, "실패", type(e).__name__, str(e)[:100]); continue
        print(f"\n== {mid}{q}: {len(h)}자, read.do {h.count('read.do')}회, <tr {h.count('<tr')}회, iframe {len(re.findall('<iframe', h))}")
        print("   title:", (re.search(r"<title>(.*?)</title>", h, re.S) or [0, ""])[1].strip()[:60])
        for m in re.findall(r'<a[^>]+href="([^"]{0,160})"[^>]*>\s*([^<]{4,60})', h)[:0]:
            pass
        links = re.findall(r'href="([^"]*(?:read|view|detail|lawmaking|opinion)[^"]{0,140})"', h)
        print("   상세 링크 예:", links[:4])
        i = h.find("tbody")
        print("   tbody 앞부분:", re.sub(r"\s+", " ", h[i:i + 900]) if i > 0 else "(tbody 없음)")
        fr = re.findall(r'<iframe[^>]+src="([^"]+)"', h)
        if fr: print("   iframe:", fr[:3])
