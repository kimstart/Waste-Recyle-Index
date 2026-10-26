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
# ① 제목 '재활용' 검색(분류 무관) 1년: 건수·낙찰방법 분포
f3 = dict(form, codeClassifyType1="", codeClassifyType2="", codeClassifyType3="", bidState="", searchBidGb="bid_gb_1", bidTitle="재활용",
          dateStart=(date.today() - timedelta(days=364)).isoformat(), dateArea="4")
ids, allrows = [], []
for pg in range(1, 40):
    f3["pageNo"] = str(pg)
    r = get(B + "/bid/bidList.do?" + urllib.parse.urlencode(f3))
    tb = r[r.find("<tbody"):r.find("</tbody>")]
    got = 0
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
        did = re.search(r"goView\('(\d+)'\)", tr)
        tds = [sq(re.sub(r"<[^>]+>", " ", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if did and did.group(1) not in ids:
            ids.append(did.group(1)); allrows.append(tds); got += 1
    if got == 0:
        break
from collections import Counter
print(f"제목 '재활용' 1년: {len(ids)}건, {pg - 1}쪽; 낙찰방법 {Counter(r[2] for r in allrows if len(r) > 2)}; 상태 {Counter(r[5] for r in allrows if len(r) > 5)}")
for r in allrows[:5] + allrows[-3:]: print("   ", r)
# 분류 확인: 앞 6건 상세의 입찰분류
for did in ids[:6]:
    d = get(B + f"/bid/bidDetail.do?bidNum={did}")
    m = re.search(r"입찰분류</th>\s*<td[^>]*>(.*?)</td>", d, re.S)
    print("   분류", did, sq(re.sub(r"<[^>]+>", " ", m.group(1))).strip() if m else None)
# ② 입찰결과 목록
for q in ({"type": "4"}, dict(f3, pageNo="1")):
    try:
        r = get(B + "/bid/bidResultList.do?" + urllib.parse.urlencode(q))
        i = r.find("<thead"); j = r.find("<tbody")
        print("\n결과목록", len(r), "머리:", sq(re.sub(r"<[^>]+>", "|", r[i:i + 900]))[:400])
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", r[j:r.find("</tbody>", j)], re.S)[:6]:
            print("   ", [sq(re.sub(r"<[^>]+>", " ", x)).strip()[:30] for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)], re.findall(r"\('(\d{10,})'", tr)[:1])
    except Exception as e:
        print("결과목록 실패", type(e).__name__)
# ③ 세대수 API 승인 여부(응답 코드만)
import os
key = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
code = re.findall(r"initList\(4, '([AB]\d+)'\)", h)[0]
for ep in ("AptBasisInfoServiceV4/getAphusBassInfoV4", "AptBasisInfoServiceV3/getAphusBassInfoV3"):
    try:
        t = urllib.request.urlopen(f"https://apis.data.go.kr/1613000/{ep}?" + urllib.parse.urlencode({"serviceKey": key, "kaptCode": code, "_type": "json"}), timeout=30).read().decode("utf8", "ignore")
        print("API", ep, t[:400].replace(key, "<KEY>"))
    except urllib.error.HTTPError as e:
        print("API", ep, "HTTP", e.code, e.read()[:200].decode("utf8", "ignore"))
    except Exception as e:
        print("API", ep, type(e).__name__)
