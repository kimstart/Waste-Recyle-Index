# -*- coding: utf-8 -*-
"""K-APT 입찰공고 접근·구조 점검"""
import re, urllib.request, urllib.parse, http.cookiejar
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def get(u, data=None, hdr=None):
    r = op.open(urllib.request.Request(u, data=data, headers={**H, **(hdr or {})}), timeout=40)
    return r.status, r.geturl(), r.read(3_000_000).decode("utf8", "ignore")
for u in ("https://www.k-apt.go.kr/", "https://www.k-apt.go.kr/bid/bidList.do", "https://www.k-apt.go.kr/bid/bidListNew.do"):
    try:
        st, fin, h = get(u)
        print(f"\n== {u}: {st} {len(h)}자 → {fin}")
        print("   title:", (re.search(r"<title>(.*?)</title>", h, re.S) or [0, ""])[1].strip()[:60])
        print("   입찰 링크:", sorted(set(re.findall(r'["\'](/bid/[A-Za-z0-9_/]+\.do[^"\']*)', h)))[:20])
        print("   ajax 후보:", sorted(set(re.findall(r'url\s*:\s*["\']([^"\']+)["\']', h)))[:20])
        print("   select:", [(n, re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', o)[:12]) for n, o in re.findall(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', h, re.S)][:8])
        print("   form input:", sorted(set(re.findall(r'<input[^>]*name="([^"]+)"', h)))[:40])
        i = h.find("매각")
        if i > 0: print("   '매각' 주변:", re.sub(r"\s+", " ", h[i - 300:i + 300]))
        i = h.find("<tbody")
        if i > 0: print("   tbody:", re.sub(r"\s+", " ", h[i:i + 1200]))
    except Exception as e:
        print(f"\n== {u}: 실패 {type(e).__name__}: {str(e)[:150]}")
