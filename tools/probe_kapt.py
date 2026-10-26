# -*- coding: utf-8 -*-
"""K-APT: 입찰 분류 코드, 매각 목록 검색 파라미터, 상세·결과 화면 구조"""
import re, json, urllib.request, urllib.parse, http.cookiejar
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
B = "https://www.k-apt.go.kr"
def get(u, data=None, hdr=None):
    r = op.open(urllib.request.Request(u, data=data, headers={**H, "Referer": B + "/bid/bidList.do", **(hdr or {})}), timeout=40)
    return r.read(3_000_000).decode("utf8", "ignore")
h = get(B + "/bid/bidList.do")
csrf = (re.search(r'name="_csrf"[^>]*value="([^"]+)"', h) or re.search(r'_csrf"\s*content="([^"]+)"', h) or [0, ""])[1]
# 분류 관련 JS·체크박스
print("분류 체크박스/라디오:", sorted(set(re.findall(r'<input[^>]*type="(?:checkbox|radio)"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', h)))[:60])
for m in re.finditer(r"getBidCodeGroup\.do", h):
    print("JS 주변:", re.sub(r"\s+", " ", h[m.start() - 600:m.start() + 400])); break
for m in re.finditer(r"function\s+(?:goSearch|search|fn_search|initList)\s*\(", h):
    print("검색 함수:", re.sub(r"\s+", " ", h[m.start():m.start() + 1500])); break
for body in ({"codeGroup": "1"}, {}):
    try:
        t = get(B + "/bid/getBidCodeGroup.do", data=urllib.parse.urlencode({**body, "_csrf": csrf}).encode(),
                hdr={"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded"})
        print("getBidCodeGroup", body, t[:1500])
    except Exception as e:
        print("getBidCodeGroup 실패", body, type(e).__name__, str(e)[:80])
# 상세 1건
m = re.search(r"goView\('(\d+)'\)", h)
if m:
    d = get(B + f"/bid/bidDetail.do?bidNum={m.group(1)}")
    rows = re.findall(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", d, re.S)
    print("\n상세 항목:", [(re.sub(r"<[^>]+>|\s+", " ", a).strip()[:20], re.sub(r"<[^>]+>|\s+", " ", b).strip()[:50]) for a, b in rows][:40])
r = get(B + "/bid/bidResultList.do")
i = r.find("<thead")
print("\n결과 목록 머리:", re.sub(r"<[^>]+>", "|", re.sub(r"\s+", " ", r[i:i + 1500]))[:600])
i = r.find("<tbody")
print("결과 목록 첫 행:", re.sub(r"<[^>]+>", "|", re.sub(r"\s+", " ", r[i:i + 1500]))[:700])
