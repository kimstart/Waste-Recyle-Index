# -*- coding: utf-8 -*-
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import official_gist as og
for name, by, date in (("전기사업법", "이상휘의원 등 10인", "2026-09-16"), ("폐기물관리법", "김기현의원 등 10인", "2026-09-07"),
                       ("자원의 절약과 재활용촉진에 관한 법률", "김은혜의원 등 15인", "2026-09-03")):
    lead = re.sub(r"의원.*", "", by)
    import urllib.parse
    j = json.loads(og.get("https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn?" + urllib.parse.urlencode(
        {"Type": "json", "pIndex": 1, "pSize": 5, "AGE": 22, "BILL_NAME": name, "PROPOSER": lead})))
    rows = j["nzmimeepazxkubdpn"][1]["row"]
    r = next((r for r in rows if r.get("PROPOSE_DT") == date), rows[0])
    t = og.text(og.get(f"{og.LIKMS}/bill/bi/popup/billSummary.do?billId={r['BILL_ID']}"))
    i = t.rfind("제안이유")
    print(f"\n### {name} {by} → {r['BILL_NAME']} {r['PROPOSE_DT']}")
    print(repr(t[i:i + 1800]))
