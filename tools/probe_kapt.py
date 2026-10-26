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
# 입찰결과 AJAX
r = get(B + "/bid/bidResultList.do")
for m in re.finditer(r"bidResultListAjax\.do", r):
    print("AJAX 주변:", sq(r[max(0, m.start() - 1500):m.start() + 800])); break
fr = re.search(r'<form name="searchForm".*?</form>', r, re.S).group(0)
names = re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', fr)
print("결과 searchForm 필드:", names)
for nm in ("codeWay", "searchDateGb", "sortType", "codeSucWay", "codeAuth"):
    m = re.search(rf'<select[^>]*name="{nm}"[^>]*>(.*?)</select>', fr, re.S)
    print(" ", nm, re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', m.group(1))[:10] if m else None)
csrf2 = re.search(r'name="_csrf"[^>]*value="([^"]+)"', r) or re.search(r'_csrf=" \+ "([0-9a-f-]+)"', r) or re.search(r'_csrf"\s*:\s*"([0-9a-f-]+)"', r)
print("csrf:", bool(csrf2))
m = re.search(r"function fnTab\((.*?)\}\s*function", r, re.S)
print("fnTab:", sq(m.group(0))[:900] if m else None)
print("탭:", re.findall(r'fnTab\((\d+)[^)]*\)[^>]*>\s*(?:<[^>]+>)*\s*([^<]{2,20})', r)[:8])
base = {"_csrf": csrf2.group(1), "searchDateGb": "bid", "searchBidGb": "bid_gb_1", "bidTitle": "재활용", "codeWay": "01",
        "dateStart": (date.today() - timedelta(days=364)).isoformat(), "dateEnd": date.today().isoformat(), "pageNo": "1",
        "pageSelect": "20", "bidState05Yn": "N", "sortType": "1", "comboSGG": "", "codeClassifyType1": "", "codeClassifyType2": "", "codeClassifyType3": "",
        "kaptdaCntStart": "", "kaptdaCntEnd": "", "searchCompany": "", "amountMin": "", "amountMax": ""}
for sido in ("11", "41"):
    for tab in ("1", "2", "3", "4"):
        q = dict(base, comboSIDO=sido, tabNum=tab)
        try:
            t = get(B + "/bid/bidResultListAjax.do", data=urllib.parse.urlencode(q).encode(),
                    hdr={"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
            trs = re.findall(r"<tr[^>]*>(.*?)</tr>", t[t.find("<tbody"):], re.S)
            tot = re.search(r"총\s*([\d,]+)\s*건|([\d,]+)\s*건", re.sub(r"<[^>]+>", " ", t))
            print(f"\n시도 {sido} 탭 {tab}: tr {len(trs)}, {tot.group(0) if tot else ''}")
            for tr in trs[:5]:
                print("   ", [sq(re.sub(r"<[^>]+>", " ", x)).strip()[:40] for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)], re.findall(r"\('(\d{10,})'", tr)[:1])
        except Exception as e:
            print("시도", sido, "탭", tab, "실패", type(e).__name__)
