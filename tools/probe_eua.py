# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get
for sym in ("CO2.L",):
    j = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=3mo&interval=1d"))
    m = j["chart"]["result"][0]["meta"]
    print({k: m.get(k) for k in ("currency", "symbol", "exchangeName", "fullExchangeName", "instrumentType", "longName", "shortName", "regularMarketPrice", "regularMarketTime")})
    c = j["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    print("최근 종가:", [round(x, 2) for x in c[-10:] if x])
