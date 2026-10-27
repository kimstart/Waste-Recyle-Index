# -*- coding: utf-8 -*-
"""K-APT 결과 공개 목록(type=3) 행에 단지코드가 있는지 (요청 1회)"""
import sys, os, re, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import UA
from datetime import date, timedelta
q = {"type": "3", "bidArea": "11|28|41", "searchBidGb": "bid_gb_1", "bidTitle": "재활용", "searchDateGb": "reg",
     "dateStart": (date.today() - timedelta(days=30)).isoformat(), "dateEnd": date.today().isoformat(), "pageNo": "1"}
h = urllib.request.urlopen(urllib.request.Request("https://www.k-apt.go.kr/bid/bidList.do?" + urllib.parse.urlencode(q),
                           headers={**UA, "Referer": "https://www.k-apt.go.kr/bid/bidList.do"}), timeout=60).read().decode("utf8", "ignore")
tb = h[h.find("<tbody"):h.find("</tbody>")]
for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)[:10]:
    sysn = re.sub(r"<[^>]+>|\s+", " ", re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)[1]).strip()
    print(sysn[:12], re.findall(r"'([AB]\d{8})'", tr), re.sub(r"\s+", " ", tr)[-260:])
