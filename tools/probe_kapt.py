# -*- coding: utf-8 -*-
import re, json, urllib.request, urllib.parse, http.cookiejar
from datetime import date, timedelta
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
B = "https://www.k-apt.go.kr"
import time
def get(u, data=None, hdr=None):
    for k in range(3):
        try:
            time.sleep(2.5)
            r = op.open(urllib.request.Request(u, data=data, headers={**H, "Referer": B + "/bid/bidList.do", **(hdr or {})}), timeout=60)
            return r.read(4_000_000).decode("utf8", "ignore")
        except Exception as e:
            print("   (재시도", k + 1, type(e).__name__, ")")
            time.sleep(8 * (k + 1))
    raise RuntimeError("K-APT 응답 없음")
sq = lambda t: re.sub(r"\s+", " ", t)
h = get(B + "/bid/bidList.do")
csrf = re.search(r'_csrf=" \+ "([0-9a-f-]+)"', h).group(1)
def codes(g):
    t = get(B + "/bid/getBidCodeGroup.do", data=f"group_id={g}&_csrf={csrf}".encode(),
            hdr={"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
    return [(x["code"], x["codeValue"]) for x in (json.loads(t) or [])]
c2 = codes("CODE_CLASSIFY_TYPE_1_02"); print("사업자 하위:", c2)
mul = next((c for c, v in c2 if "물품" in v), None)
c3 = codes(f"CODE_CLASSIFY_TYPE_1_02_{mul}") if mul else []; print("물품 하위:", c3)
mae = next((c for c, v in c3 if "매각" in v), None)
f = re.search(r'<form name="searchForm".*?</form>', h, re.S).group(0)
names = re.findall(r'<(?:input|select)[^>]*name="([^"]+)"[^>]*?(?:value="([^"]*)")?', f)
print("searchForm 필드:", names[:60])
for nm in ("searchDateGb", "bidState", "pageSelect", "codeAuth", "codeWay", "codeSucWay", "searchBidGb"):
    m = re.search(rf'<select[^>]*name="{nm}"[^>]*>(.*?)</select>', h, re.S)
    print(" ", nm, re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', m.group(1))[:12] if m else None)
print("type input:", re.findall(r'<input[^>]*name="type"[^>]*>', h))
print("검색 버튼:", re.findall(r'onclick="(initList\([^"]*)"', h)[:10])
form = {n: v for n, v in names}
form.update({"_csrf": csrf, "bidArea": "11|28|41", "codeClassifyType1": "02", "codeClassifyType2": mul, "codeClassifyType3": mae,
             "dateStart": (date.today() - timedelta(days=90)).isoformat(), "dateEnd": date.today().isoformat(), "dateArea": "2", "pageNo": "1", "type": "4", "searchDateGb": "reg", "pageSelect": "10"})
for meth in ("GET", "POST"):
    try:
        q = urllib.parse.urlencode(form)
        r = get(B + "/bid/bidList.do" + ("?" + q if meth == "GET" else ""), data=q.encode() if meth == "POST" else None,
                hdr={"Content-Type": "application/x-www-form-urlencoded"} if meth == "POST" else None)
        rows = re.findall(r'<tr[^>]*dataId="(\d+)"(.*?)</tr>', r, re.S)
        tot = re.search(r"총\s*<[^>]*>?\s*([\d,]+)\s*건|전체\s*([\d,]+)\s*건|total[^\d]{0,20}([\d,]+)", r)
        print(f"\n{meth}: 응답 {len(r)}자, 행 {len(rows)}개, 총건수 표시 {tot.group(0)[:40] if tot else None}")
        i = r.find("<tbody"); print("   tbody:", sq(r[i:i + 600]))
        for i, (did, tr) in enumerate(rows[:12]):
            tds = [sq(re.sub(r"<[^>]+>", " ", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            print("  ", did, tds)
        if rows: break
    except Exception as e:
        print(meth, "실패", type(e).__name__, str(e)[:100])
# 입찰결과 화면 구조
r = get(B + "/bid/bidResultList.do")
print("결과 페이지", len(r), "title:", (re.search(r"<title>(.*?)</title>", r, re.S) or [0, ""])[1].strip()[:40])
print("forms:", re.findall(r"<form[^>]*>", r)[:6])
for kw in ("낙찰금액", "낙찰업체", "낙찰자", "개찰", "goView", "goResult", "resultView", "tbody", "<table"):
    i = r.find(kw); print(f"[{kw}] {r.count(kw)}회", sq(r[max(0, i - 200):i + 500])[:700] if i >= 0 else "")
i = r.find("function initList(")
print("결과 initList:", sq(r[i:i + 1500]) if i > 0 else None)
print("결과 링크:", sorted(set(re.findall(r'["\'](/bid/[A-Za-z0-9_/]+\.do)', r))))
