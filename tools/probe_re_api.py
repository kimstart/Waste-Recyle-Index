# -*- coding: utf-8 -*-
"""순환자원정보센터 전자입찰·수의견적 API 응답 구조 확인 (키 값은 출력하지 않음)"""
import os, json, urllib.parse, urllib.request
DK = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
B = "https://apis.data.go.kr/B552584/kecoapi"
for path in ("bidPbancService/getBidPbancInfo", "bidPbancService/getBidPbancRsltInfo",
             "pvctEstmtPbancService/getPvctEstmtPbancInfo", "pvctEstmtPbancService/getPvctEstmtPbancRsltInfo"):
    for extra in ({"returnType": "json"}, {"_type": "json"}):
        q = {"serviceKey": DK, "pageNo": 1, "numOfRows": 3, **extra}
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"{B}/{path}?" + urllib.parse.urlencode(q), headers={"User-Agent": "Mozilla/5.0"}), timeout=60)
            body = r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            body = f"HTTP {e.code} " + e.read().decode("utf-8", "ignore")
        except Exception as e:
            body = f"{type(e).__name__} {e}"
        body = body.replace(DK, "<KEY>")
        print(f"== {path} {extra}")
        print("   " + " ".join(body[:3500].split()))
        if body.lstrip().startswith("{"):
            break
