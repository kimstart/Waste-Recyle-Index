# -*- coding: utf-8 -*-
"""한 공고의 첨부에서 물량 관련 문구가 어떻게 적혀 있는지 확인"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from doc_qty import download, text_of, find_qty
no = sys.argv[1]
b = next(x for x in json.load(open("data/services.json"))["items"] if x.get("no") == no)
for name, url in b.get("docs", []):
    t = re.sub(r"\s+", " ", text_of(download(url)))
    print(f"\n### {name}: 본문 {len(t)}자, find_qty → {find_qty(t)[:3]}")
    for m in re.finditer(r"톤|㎏|kg|ton|물량|처리량|과업량|위탁량|수량", t):
        print("   …", t[max(0, m.start() - 70):m.end() + 50])
