# -*- coding: utf-8 -*-
"""K-APT 검색 형식 확인 (출력이 길어도 구조 파악용)"""
import re, json, urllib.request, urllib.parse, http.cookiejar
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
B = "https://www.k-apt.go.kr"
def get(u, data=None, hdr=None):
    r = op.open(urllib.request.Request(u, data=data, headers={**H, "Referer": B + "/bid/bidList.do", **(hdr or {})}), timeout=40)
    return r.read(3_000_000).decode("utf8", "ignore")
sq = lambda t: re.sub(r"\s+", " ", t)
h = get(B + "/bid/bidList.do")
csrf = re.search(r'_csrf=" \+ "([0-9a-f-]+)"', h) or re.search(r'name="_csrf"[^>]*value="([^"]+)"', h)
csrf = csrf.group(1) if csrf else ""
print("csrf 길이", len(csrf))
print("forms:", re.findall(r"<form[^>]*>", h)[:6])
for nm in ("codeClassifyType1", "codeClassifyType2", "codeClassifyType3"):
    m = re.search(rf'<select[^>]*name="{nm}"[^>]*>(.*?)</select>', h, re.S)
    print(nm, re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', m.group(1)) if m else None)
m = re.search(r'id="areaCount"(.*?)</ul>', h, re.S)
print("areaCount:", sq(m.group(1))[:1500] if m else None)
i = h.find("function initList(")
print("\ninitList 전체:", sq(h[i:i + 6000]))
for g in ("CODE_CLASSIFY_TYPE_1", "CODE_CLASSIFY_TYPE_1_1", "CODE_CLASSIFY_TYPE_1_01"):
    try:
        t = get(B + "/bid/getBidCodeGroup.do", data=f"group_id={g}&_csrf={csrf}".encode(),
                hdr={"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        print("\n코드", g, t[:800])
    except Exception as e:
        print("\n코드", g, "실패", type(e).__name__)
