# -*- coding: utf-8 -*-
"""순환자원정보센터 API의 물품분류·입찰구분 분포 확인 (1회 점검)"""
import os, json, urllib.parse, urllib.request, collections
DK = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
B = "https://apis.data.go.kr/B552584/kecoapi"
for path in ("bidPbancService/getBidPbancInfo", "pvctEstmtPbancService/getPvctEstmtPbancInfo"):
    rows = []
    for page in (1, 2, 3):
        q = {"serviceKey": DK, "pageNo": page, "numOfRows": 1000, "returnType": "json"}
        try:
            j = json.loads(urllib.request.urlopen(f"{B}/{path}?" + urllib.parse.urlencode(q), timeout=90).read().decode("utf-8", "ignore"))
            rows += j.get("body", {}).get("items") or []
        except Exception as e:
            print("fail", path, page, e); break
    c = collections.Counter((x.get("cmdtyLclsfNm"), x.get("cmdtyMclsfNm"), x.get("cmdtySclsfNm"), x.get("bidSeNm") or x.get("estmtSeNm")) for x in rows)
    print("==", path, len(rows))
    for k, v in c.most_common(80):
        print(v, k)
    org = [x for x in rows if any(w in (x.get("pbancNm","")+str(x.get("cmdtyMclsfNm"))+str(x.get("cmdtySclsfNm"))) for w in ("음식","음폐","슬러지","오니","동식물","유기","가축","분뇨","찌꺼기","바이오"))]
    print("-- 유기성 후보", len(org))
    for x in org[:25]:
        print(x.get("bidBgngDt") or x.get("pbancBgngDt"), "|", x.get("cmdtyMclsfNm"), "/", x.get("cmdtySclsfNm"), "|", x.get("bidSeNm") or x.get("estmtSeNm"), "|", x.get("pbancIsrNm"), "|", x.get("pbancNm"))
