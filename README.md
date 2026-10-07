# 폐플라스틱·바이오가스 데일리 리포트

폐플라스틱·바이오가스 관련 시장 지표와 뉴스를 매일 자동으로 모아 한 곳에 게시하는 웹페이지입니다.
서버 없이 GitHub Actions(자동 수집)와 GitHub Pages(게시)만으로 동작합니다.

- 폐플라스틱: `plastic.html`
- 바이오가스: `biogas.html`

## 지표

| 페이지 | 구분 | 지표 | 출처 |
|---|---|---|---|
| 폐플라스틱 | 월간 | 국내 재생원료 단가 (압축·플레이크·펠렛, 전국평균 원/kg) | 한국환경공단 순환자원정보센터 |
| 폐플라스틱 | 일간 | 중국 신재 선물 PET 병 칩·PE·PP·PVC (위안/톤, 원/kg 환산) | 정저우·다롄 상품거래소 (Sina Finance) |
| 폐플라스틱 | (환산용) | 원/위안 환율 | 수출입은행(키 있을 때) → ECB → Yahoo |
| 바이오가스 | 일간 | REC 현물 평균가 | 한국전력거래소 |
| 바이오가스 | 일간 | TTF 천연가스 | ICE Endex (Yahoo Finance) |
| 바이오가스 | 일간 | KCU 상쇄배출권 | 한국거래소 배출권시장 정보플랫폼 |
| 바이오가스 | 월간 | 도시가스용 천연가스 도매요금 평균 | 한국가스공사 |
| 바이오가스 | 분기 | 프랑스 바이오가스 원산지보증서(GO) 경매 기준가격 | EEX |
| 바이오가스 | (환산용) | 원/유로 환율, 도시가스 공급 예상열량(MJ/N㎥) | ECB·수출입은행, 한국가스공사 |

TTF·GO는 €/MWh × 원/유로 × 열량 ÷ 3,600, 도매요금은 원/MJ × 열량으로 원/㎥ 환산합니다.

## 파일 구성

```
plastic.html, biogas.html   화면 (공통: assets/board.js, assets/board.css)
collect_plastic.py          폐플라스틱 지표 수집 → data/plastic.json
collect_biogas.py           바이오가스 지표 수집 → data/biogas.json
collect_news.py             뉴스 수집 → data/news_plastic.json, data/news_biogas.json
common.py, sources.py       공통 함수, 환율·유가·Yahoo 시세
history/                    날짜별 보관본 (화면에서 조회일자를 바꾸면 이 파일을 읽음)
.github/workflows/          자동 실행 일정 (지표: 하루 5회, 뉴스: 하루 2회)
```

## 운영 메모

- 수집에 실패한 지표는 이전 값을 그대로 유지합니다. 실행 기록은 GitHub의 Actions 탭에서 볼 수 있습니다.
- 선택 사항: 저장소 Settings → Secrets and variables → Actions 에 아래 키를 넣으면 더 정확한 출처를 씁니다.
  - `KOREAEXIM_KEY`: 한국수출입은행 환율 API (없으면 ECB 기준환율 사용)
  - `DATA_GO_KR_KEY`: 공공데이터포털 (REC 홈페이지 수집 실패 시 대체용)
- 뉴스 키워드·매체 목록은 `collect_news.py` 맨 위 `CONFIG` 에서 고칠 수 있습니다.
- 지표 설명(비고)은 각 html 파일 아래쪽 `rows` 목록의 `why` 글자를 고치면 됩니다.
