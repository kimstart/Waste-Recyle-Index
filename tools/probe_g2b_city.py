# -*- coding: utf-8 -*-
"""평택·오산 재활용 관련 나라장터 공고 확인 (1회용 점검)"""
import os, json, urllib.parse, urllib.request
from datetime import datetime, timedelta
DK = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
now = datetime.utcnow() + timedelta(hours=9)
hits = {}
for kind in ("Servc", "Thng"):
    for k in range(0, 420, 30):
        e, s = now - timedelta(days=k), now - timedelta(days=k + 30)
        for kw in ("재활용", "선별", "폐기물"):
            q = {"serviceKey": DK, "pageNo": 1, "numOfRows": 999, "type": "json", "inqryDiv": 1,
                 "inqryBgnDt": s.strftime("%Y%m%d0000"), "inqryEndDt": e.strftime("%Y%m%d2359"), "bidNtceNm": kw}
            url = f"https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfo{kind}PPSSrch?" + urllib.parse.urlencode(q)
            try:
                j = json.loads(urllib.request.urlopen(url, timeout=40).read().decode("utf-8", "ignore"))
                its = j.get("response", {}).get("body", {}).get("items") or []
            except Exception as ex:
                print("fail", kind, kw, s.date(), type(ex).__name__); continue
            for x in its:
                t = f"{x.get('bidNtceNm','')} | {x.get('ntceInsttNm','')} | {x.get('dminsttNm','')}"
                if any(c in t for c in ("평택", "오산")):
                    hits[x.get("bidNtceNo")] = f"{x.get('bidNtceDt','')[:10]} [{kind}] {t} | 추정가 {x.get('presmptPrce')}"
for v in sorted(hits.values(), reverse=True):
    print(v)
print("총", len(hits))
