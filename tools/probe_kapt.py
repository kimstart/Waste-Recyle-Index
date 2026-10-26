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
# 1년 전체(상태 무관) 페이지 넘기기
f2 = dict(form, bidState="", dateStart=(date.today() - timedelta(days=364)).isoformat(), dateArea="4")
ids, allrows = [], []
for pg in range(1, 15):
    f2["pageNo"] = str(pg)
    r = get(B + "/bid/bidList.do?" + urllib.parse.urlencode(f2))
    tb = r[r.find("<tbody"):r.find("</tbody>")]
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)
    got = 0
    for tr in trs:
        did = re.search(r"goView\('(\d+)'\)", tr)
        tds = [sq(re.sub(r"<[^>]+>", " ", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if did and did.group(1) not in ids:
            ids.append(did.group(1)); allrows.append(tds); got += 1
    print(f"  {pg}쪽: tr {len(trs)}, 신규 {got}")
    if got == 0:
        break
print("1년 합계", len(ids), "건; 상태 분포:", {x: sum(1 for r in allrows if len(r) > 5 and r[5] == x) for x in set(r[5] for r in allrows if len(r) > 5)})
for r in allrows[-6:]: print("   ", r)
for did in [i for i, r in zip(ids, allrows) if len(r) > 5 and '마감' in r[5]][:2] or ids[-2:]:
    d = get(B + f"/bid/bidDetail.do?bidNum={did}")
    rows = re.findall(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", d, re.S)
    print(f"\n상세 {did}:", [(sq(re.sub(r"<[^>]+>", " ", a)).strip()[:16], sq(re.sub(r"<[^>]+>", " ", b)).strip()[:70]) for a, b in rows][:45])
    for kw in ("낙찰", "개찰", "결과"):
        for m in list(re.finditer(kw, d))[:2]:
            print(f"   [{kw}]", sq(re.sub(r"<[^>]+>", " ", d[m.start() - 150:m.start() + 250]))[:300])
    print("   첨부:", re.findall(r"(?:fileDown|download)[^\"']*\(([^)]*)\)", d)[:5], re.findall(r'href="([^"]*(?:download|fileDown)[^"]*)"', d)[:5])
# 세대수: K-APT 단지정보 / 공공데이터 API
import os
code = re.findall(r"initList\(4, '([AB]\d+)'\)", h)[0]
for u in (f"{B}/apt/danjiInfo.do?kaptCode={code}", f"{B}/kaptinfo/openkaptinfo.do?kapt_code={code}", f"{B}/cmmn/kaptInfo.do?kapt_code={code}"):
    try:
        t = get(u); i = t.find("세대")
        print("\n단지정보", u.split(".kr")[1], len(t), sq(re.sub(r"<[^>]+>", " ", t[i - 200:i + 300]))[:400] if i > 0 else "세대 없음")
    except Exception as e:
        print("\n단지정보", u.split(".kr")[1], "실패", type(e).__name__)
key = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
for ep in ("AptBasisInfoServiceV4/getAphusBassInfoV4", "AptBasisInfoServiceV3/getAphusBassInfoV3"):
    try:
        t = get(f"https://apis.data.go.kr/1613000/{ep}?" + urllib.parse.urlencode({"serviceKey": key, "kaptCode": code, "_type": "json"}))
        print("\nAPI", ep, t[:500].replace(key, "<KEY>"))
    except Exception as e:
        print("\nAPI", ep, "실패", type(e).__name__, str(e)[:80])
