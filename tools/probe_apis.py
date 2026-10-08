# -*- coding: utf-8 -*-
"""API 키 동작 확인용 (키 값은 출력하지 않음). 결과 → logs/probe_apis.log"""
import os, re, json, urllib.parse, urllib.request
from datetime import datetime, timedelta

DK = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
LK = os.environ.get("LAW_API_KEY", "")
now = datetime.utcnow() + timedelta(hours=9)


def call(label, url, params, key_name="serviceKey", key=DK, show=1500):
    if not key:
        print(f"== {label}: 키 없음"); return None
    q = dict(params); q[key_name] = key
    full = url + "?" + urllib.parse.urlencode(q)
    for attempt in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(full, headers={"User-Agent": "Mozilla/5.0"}), timeout=60)
            body, code = r.read().decode("utf-8", "ignore"), r.status
            break
        except urllib.error.HTTPError as ex:
            body, code = ex.read().decode("utf-8", "ignore"), ex.code
            break
        except Exception as ex:
            body, code = f"{type(ex).__name__} {ex}", 0
    body = body.replace(key, "<KEY>")
    print(f"== {label}: HTTP {code}")
    print("   " + " ".join(body[:show].split()))
    return body


A = "https://apis.data.go.kr"
call("환경공단 가격", A + "/B552584/reutilMrktPrcExmn/getlist", {"pageNo": 1, "numOfRows": 5, "returnType": "json"}, show=2500)
b, e = (now - timedelta(days=90)).strftime("%Y%m%d0000"), now.strftime("%Y%m%d2359")
for kw in ("매각", "재활용"):
    call(f"나라장터 입찰공고 용역 '{kw}' 90일", A + "/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch",
         {"pageNo": 1, "numOfRows": 2, "type": "json", "inqryDiv": 1, "inqryBgnDt": b, "inqryEndDt": e, "bidNtceNm": kw}, show=4000)
call("나라장터 낙찰 용역 '매각' 90일", A + "/1230000/as/ScsbidInfoService/getScsbidListSttusServcPPSSrch",
     {"pageNo": 1, "numOfRows": 2, "type": "json", "inqryDiv": 1, "inqryBgnDt": b, "inqryEndDt": e, "bidNtceNm": "매각"}, show=3000)
for hs in ("3915", "391590", "3901100000", "3907610000"):
    call(f"관세청 {hs}", A + "/1220000/Itemtrade/getItemtradeList",
         {"strtYymm": "202601", "endYymm": "202603", "hsSgn": hs}, show=1200)
call("법령 시행령", "https://www.law.go.kr/DRF/lawSearch.do", {"target": "law", "type": "JSON", "query": "자원의 절약과 재활용촉진에 관한 법률 시행령", "display": 3}, key_name="OC", key=LK, show=1500)
call("행정규칙 재활용의무율", "https://www.law.go.kr/DRF/lawSearch.do", {"target": "admrul", "type": "JSON", "query": "재활용의무", "display": 5}, key_name="OC", key=LK, show=2000)
call("행정규칙 재생원료", "https://www.law.go.kr/DRF/lawSearch.do", {"target": "admrul", "type": "JSON", "query": "재생원료", "display": 5}, key_name="OC", key=LK, show=2000)
