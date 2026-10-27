# -*- coding: utf-8 -*-
"""국토교통부 공동주택 기본정보·단지목록 API 사용 가능 여부 (키는 출력하지 않음)"""
import os, json, urllib.parse, urllib.request
K = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
def call(path, **p):
    u = f"https://apis.data.go.kr/1613000/{path}?" + urllib.parse.urlencode({"serviceKey": K, "_type": "json", **p})
    try:
        t = urllib.request.urlopen(u, timeout=30).read().decode("utf8", "ignore")
    except urllib.error.HTTPError as e:
        t = f"HTTP {e.code} " + e.read()[:300].decode("utf8", "ignore")
    except Exception as e:
        t = type(e).__name__
    print(f"\n== {path} {p}\n   {t[:700].replace(K, '<KEY>')}")
call("AptBasisInfoServiceV5/getAphusBassInfoV5", kaptCode="A15876402")
call("AptBasisInfoServiceV5/getAphusDtlInfoV5", kaptCode="A15876402")
call("AptListService3/getTotalAptList3", pageNo=1, numOfRows=3)
call("AptListService3/getSigunguAptList3", sigunguCode="41590", pageNo=1, numOfRows=3)
