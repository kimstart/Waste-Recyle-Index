# -*- coding: utf-8 -*-
"""물량 미확인 공고 재시험(새 표 머리글 규칙) + 여전히 못 찾는 건의 '톤' 문맥"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from doc_qty import download, text_of, qty_from_docs
items = [x for x in json.load(open("data/services.json"))["items"] if x.get("qty_checked") and not x.get("qty_t") and x.get("docs")]
ok = 0
for b in items:
    est = b.get("est") if (b.get("est") or 0) >= 3e6 else None
    q, note = qty_from_docs(b["docs"], est)
    if q:
        ok += 1; print(f" ✓ {b['title'][:34]:34} | {q:,.1f}톤 | 추정 {est} | {note[:90]}")
        continue
    print(f" ✗ {b['title'][:34]:34} | 추정 {b.get('est')}")
    for name, url in b["docs"][:3]:
        if not re.search(r"\.(hwpx?|pdf)$", name, re.I): continue
        try:
            t = re.sub(r"\s+", " ", text_of(download(url)))
        except Exception:
            continue
        hits = [t[max(0, m.start() - 60):m.end() + 40] for m in re.finditer(r"\d[\d,.]*\s*(?:톤|ton|㎏|kg)|(?:물량|처리량|반입량|발생량)", t)][:4]
        for h in hits: print("      …", h)
print(f"재시험: {len(items)}건 중 {ok}건 새로 확인")
