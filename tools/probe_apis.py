# -*- coding: utf-8 -*-
"""API 키 동작 확인용 (키 값은 출력하지 않음). 결과 → logs/probe_apis.log"""
import os, re, urllib.parse, urllib.request
from datetime import datetime, timedelta

DK = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
LK = os.environ.get("LAW_API_KEY", "")
now = datetime.utcnow() + timedelta(hours=9)
b, e = (now - timedelta(days=30)).strftime("%Y%m%d0000"), now.strftime("%Y%m%d2359")


def call(label, url, params, key_name="serviceKey", key=DK):
    if not key:
        print(f"== {label}: 키 없음"); return
    q = dict(params); q[key_name] = key
    full = url + "?" + urllib.parse.urlencode(q)
    try:
        req = urllib.request.Request(full, headers={"User-Agent": "Mozilla/5.0"})
        r = urllib.request.urlopen(req, timeout=30)
        body = r.read().decode("utf-8", "ignore"); code = r.status
    except urllib.error.HTTPError as ex:
        body, code = ex.read().decode("utf-8", "ignore"), ex.code
    except Exception as ex:
        print(f"== {label}: 접속 실패 {type(ex).__name__} {ex}"); return
    body = body.replace(key, "<KEY>") if key else body
    tot = re.search(r'"?totalCount"?\s*[:>]\s*"?(\d+)', body)
    msg = re.search(r'(resultMsg|returnAuthMsg|errMsg|result)"?\s*[:>]\s*"?([^"<,}]+)', body)
    print(f"== {label}: HTTP {code} | 전체 {tot.group(1) if tot else '-'} | {msg.group(2).strip() if msg else ''}")
    print("   " + " ".join(body[:700].split()))


A = "https://apis.data.go.kr"
call("환경공단 재활용가능자원 가격", A + "/B552584/reutilMrktPrcExmn/getlist", {"pageNo": 1, "numOfRows": 3, "returnType": "json"})
for kind in ("Thng", "Servc"):
    call(f"나라장터 입찰공고({kind}) '매각' 검색", A + f"/1230000/ad/BidPublicInfoService/getBidPblancListInfo{kind}PPSSrch",
         {"pageNo": 1, "numOfRows": 3, "type": "json", "inqryDiv": 1, "inqryBgnDt": b, "inqryEndDt": e, "bidNtceNm": "매각"})
for path in ("/1230000/as/ScsbidInfoService", "/1230000/ScsbidInfoService"):
    call(f"나라장터 낙찰({path})", A + path + "/getScsbidListSttusThngPPSSrch",
         {"pageNo": 1, "numOfRows": 3, "type": "json", "inqryDiv": 1, "inqryBgnDt": b, "inqryEndDt": e})
call("관세청 품목별 수출입실적 PP(3902.10)", A + "/1220000/Itemtrade/getItemtradeList",
     {"strtYymm": (now - timedelta(days=200)).strftime("%Y%m"), "endYymm": now.strftime("%Y%m"), "hsSgn": "3902100000"})
for tgt in ("law", "admrul"):
    call(f"법령정보({tgt}) 자원재활용", "https://www.law.go.kr/DRF/lawSearch.do",
         {"target": tgt, "type": "XML", "query": "자원의 절약과 재활용촉진", "display": 3}, key_name="OC", key=LK)
