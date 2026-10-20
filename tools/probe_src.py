# -*- coding: utf-8 -*-
import os, re, json, urllib.parse, urllib.request
LAW = os.environ.get("LAW_API_KEY", "")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"}
def get(u, n=3_000_000, data=None, hdr=None):
    u = urllib.parse.quote(u, safe=":/?&=%#;,+@")
    with urllib.request.urlopen(urllib.request.Request(u, data=data, headers={**H, **(hdr or {})}), timeout=40) as r:
        return r.read(n).decode("utf8", "ignore")
bid = "PRC_2CE1D6BED1FC48AF8E69CB92893E04"
B = "https://likms.assembly.go.kr"
h = get(f"{B}/bill/bi/billDetailPage.do?billId={bid}")
js = re.findall(r'<script[^>]+src="([^"]+)"', h)
print("scripts:", js[:30])
inline = " ".join(re.findall(r"<script[^>]*>(.*?)</script>", h, re.S))
print("inline url들:", sorted(set(re.findall(r"['\"]((?:/bill)?/[A-Za-z0-9_/]+\.(?:do|json))['\"]", inline)))[:40])
for s in js:
    if "bill" in s.lower() or "detail" in s.lower():
        try:
            t = get(B + s if s.startswith("/") else s)
            print("  ", s, len(t), sorted(set(re.findall(r"['\"]((?:/bill)?/[A-Za-z0-9_/]+\.(?:do|json))['\"]", t)))[:30])
        except Exception as e:
            print("  ", s, "실패", type(e).__name__)
for path in ("/bill/summaryPopup.do", "/bill/bi/popup/summaryPopup.do", "/bill/bi/bill/detail/summary.json", "/bill/bi/bill/detail/billSummary.do"):
    try:
        t = get(f"{B}{path}?billId={bid}")
        i = t.find("제안이유")
        print(path, len(t), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t[i:i + 500])) if i >= 0 else "제안이유 없음")
    except Exception as e:
        print(path, "실패", type(e).__name__, str(e)[:60])
# 열린국회: 의안 상세 API 후보
for api in ("BILLINFODETAIL", "TVBPMBILL11", "BPMBILLSUMMARY"):
    try:
        t = get(f"https://open.assembly.go.kr/portal/openapi/{api}?Type=json&pIndex=1&pSize=1&BILL_ID={bid}")
        print(api, t[:400])
    except Exception as e:
        print(api, "실패", type(e).__name__)
if LAW:
    for nw in ("2", "1"):
        s = get(f"https://www.law.go.kr/DRF/lawSearch.do?OC={LAW}&target=law&type=JSON&nw={nw}&query=폐기물의 국가 간 이동 및 그 처리에 관한 법률")
        print(f"\nnw={nw}:", [(r.get("공포일자"), r.get("시행일자"), r.get("현행연혁코드"), r.get("법령일련번호")) for r in (json.loads(s).get("LawSearch", {}).get("law") or [])][:8] if s.strip().startswith("{") else s[:200].replace(LAW, "<KEY>"))
h = get("https://opinion.lawmaking.go.kr/gcom/admpp/list?asndOfiNm=기후에너지환경부")
m = re.search(r'href="([^"]*admpp/\d+[^"]*)"[^>]*title="[^"]*분리수거', h)
u = m.group(1).replace("&amp;", "&")
d = get("https://opinion.lawmaking.go.kr" + u if u.startswith("/") else u)
i = d.find("주요내용")
print("\n행정예고 상세:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", d[max(0, i - 600):i + 1000]))[:1200] if i > 0 else d[:300])
