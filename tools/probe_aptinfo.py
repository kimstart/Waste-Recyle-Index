# -*- coding: utf-8 -*-
"""공동주택 기본정보 V5 승인 반영 여부·응답 항목 (키는 출력하지 않음)"""
import os, json, urllib.parse, urllib.request
K = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
for c in ("A10023559", "A44690205"):
    u = "https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5?" + urllib.parse.urlencode({"serviceKey": K, "kaptCode": c, "_type": "json"})
    try:
        t = urllib.request.urlopen(u, timeout=30).read().decode("utf8", "ignore")
    except urllib.error.HTTPError as e:
        t = f"HTTP {e.code} " + e.read()[:300].decode("utf8", "ignore")
    print(c, t[:1500].replace(K, "<KEY>"))
