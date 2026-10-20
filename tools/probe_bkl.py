# -*- coding: utf-8 -*-
"""태평양(BKL) 환경 정책 동향 PDF 좌표 구조 점검"""
import io, urllib.request, pdfplumber
H = {"User-Agent": "Mozilla/5.0"}
b = urllib.request.urlopen(urllib.request.Request("https://www.bkl.co.kr/newsLetter/itemUrl.do?itemNo=6820", headers=H), timeout=60).read()
with pdfplumber.open(io.BytesIO(b)) as pdf:
    for i in (19, 20, 23):
        p = pdf.pages[i]
        print(f"\n## p{i + 1} size {p.width:.0f}x{p.height:.0f}")
        hs = sorted({round(e["top"]) for e in p.horizontal_edges if e["x1"] - e["x0"] > 200})
        vs = sorted({round(e["x0"]) for e in p.vertical_edges if e["bottom"] - e["top"] > 20})
        print("  가로선 y:", hs[:40])
        print("  세로선 x:", vs)
        ws = p.extract_words(keep_blank_chars=False, use_text_flow=False)
        lines = {}
        for w in ws:
            lines.setdefault(round(w["top"] / 3), []).append(w)
        for k in sorted(lines)[:45]:
            l = sorted(lines[k], key=lambda w: w["x0"])
            print(f"  y{l[0]['top']:.0f}: " + " ".join(f"[{w['x0']:.0f}]{w['text'][:10]}" for w in l)[:190])
