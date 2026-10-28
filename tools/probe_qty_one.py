# -*- coding: utf-8 -*-
"""물량 미확인 공고들의 첨부: 본문 글자 수(0이면 스캔 PDF)와 '○○량(톤)' 표 머리글 주변"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from doc_qty import download, text_of
items = [x for x in json.load(open("data/services.json"))["items"] if x.get("qty_checked") and not x.get("qty_t") and x.get("docs")]
print("물량 미확인", len(items), "건")
scan = tbl = other = 0
for b in items:
    kinds = []
    for name, url in b["docs"][:4]:
        if not re.search(r"\.(hwpx?|pdf)$", name, re.I) or re.search(r"예규|유의서|일반조건|청렴|서약|제출서류", name):
            continue
        try:
            t = re.sub(r"\s+", " ", text_of(download(url)))
        except Exception as e:
            kinds.append(f"{name[-12:]}:실패"); continue
        h = re.search(r"(?:량|물량|수량)\s*\(\s*(?:톤|ton|kg|㎏|t)\s*\)", t, re.I)
        kinds.append(f"{name.split('.')[-1]}:{len(t)}자{'·표머리글' if h else ''}")
        if h and b["no"] in ("R26BK01318769",) or (h and tbl < 6):
            print("   [표]", b["title"][:30], "…", t[h.start() - 30:h.end() + 220])
    if any(k.endswith(":0자") for k in kinds): scan += 1
    if any("표머리글" in k for k in kinds): tbl += 1
    print(f" {b['title'][:36]:36} | {' , '.join(kinds)}")
print(f"스캔 PDF 포함 {scan}건, 표 머리글 단위 {tbl}건")
