# -*- coding: utf-8 -*-
"""태평양(BKL) 환경 정책 동향 PDF 표 구조 점검 (셀은 앞부분만 출력)"""
import io, urllib.request, pdfplumber
H = {"User-Agent": "Mozilla/5.0"}
b = urllib.request.urlopen(urllib.request.Request("https://www.bkl.co.kr/newsLetter/itemUrl.do?itemNo=6820", headers=H), timeout=60).read()
with pdfplumber.open(io.BytesIO(b)) as pdf:
    print("pages", len(pdf.pages))
    for i, p in enumerate(pdf.pages):
        tx = (p.extract_text() or "").splitlines()
        heads = [l for l in tx if l.strip()[:3] in ("I. ", "II.", "III", "IV.", "V. ")]
        tabs = p.extract_tables()
        print(f"\n## p{i + 1} 표 {len(tabs)}개 · 제목줄 {heads[:3]}")
        for t in tabs:
            print(f"  표 {len(t)}행 × {len(t[0]) if t else 0}열")
            for r in t[:4]:
                print("   ", [(c or "").replace("\n", "⏎")[:28] for c in r])
