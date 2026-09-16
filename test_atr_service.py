from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from weekly.services.atr_service import ATRError, ATRService, ATRSettings

ET = ZoneInfo("America/New_York")

def session(day):
    return SimpleNamespace(date=day, open=datetime(day.year,day.month,day.day,9,30,tzinfo=ET), close=datetime(day.year,day.month,day.day,16,0,tzinfo=ET))

def minute_bar(start_at, price):
    return SimpleNamespace(start_at=start_at,end_at=start_at+timedelta(minutes=1),open=price,high=price+0.5,low=price-0.5,close=price,volume=100.0)

def minute_series(sessions, drift=0.01):
    bars=[]; price=100.0
    for s in sessions:
        t=s.open
        while t < s.close:
            bars.append(minute_bar(t,price)); price += drift; t += timedelta(minutes=1)
    return bars

def main():
    cfg=ATRSettings.from_config(); assert cfg.atr_1h_period==14 and cfg.atr_15m_period==14
    print("1. weekly config ATR periods = 14/14: PASS")
    svc=ATRService(cfg)
    bars=[]; base=datetime(2026,9,1,9,30,tzinfo=ET)
    for i in range(15):
        p=100.0+i
        bars.append(SimpleNamespace(start_at=base+timedelta(hours=i), high=p+1.0, low=p-1.0, close=p))
    atr,reason=ATRService._calculate_atr(bars=bars,period=14,insufficient_reason="INSUFFICIENT")
    assert atr==2.0 and reason=="ATR_AVAILABLE"
    print("2. True Range + arithmetic mean ATR(14): PASS")
    atr,reason=ATRService._calculate_atr(bars=bars[:14],period=14,insufficient_reason="INSUFFICIENT")
    assert atr is None and reason=="INSUFFICIENT"
    print("3. ATR requires N+1 completed bars: PASS")
    sessions=[session(date(2026,9,10)),session(date(2026,9,11)),session(date(2026,9,14))]
    mins=minute_series(sessions)
    as_of=datetime(2026,9,14,13,7,tzinfo=ET)
    r=svc.evaluate(as_of=as_of,trading_date_et=date(2026,9,14),calendar=sessions,minute_bars=mins)
    assert r.atr_15m is not None and r.atr_1h is not None
    assert r.atr_15m_reason=="ATR_AVAILABLE" and r.atr_1h_reason=="ATR_AVAILABLE"
    print("4. ATR_15m and ATR_1H calculate from completed RTH bars: PASS")
    assert r.fifteen_minute_bars[-1].end_at==datetime(2026,9,14,13,0,tzinfo=ET)
    print("5. partial 15m window excluded: PASS")
    assert r.hourly_bars[-1].end_at==datetime(2026,9,14,12,30,tzinfo=ET)
    print("6. partial 1H window excluded / session-open anchored: PASS")
    assert r.fifteen_minute_bars[0].start_at.date()==date(2026,9,10)
    assert r.hourly_bars[0].start_at.date()==date(2026,9,10)
    print("7. ATR history crosses week boundary / no reset: PASS")
    one=[session(date(2026,9,14))]
    sparse=svc.evaluate(as_of=datetime(2026,9,14,10,0,tzinfo=ET),trading_date_et=date(2026,9,14),calendar=one,minute_bars=minute_series(one,0.0))
    assert sparse.atr_1h is None and sparse.atr_15m is None
    assert sparse.atr_1h_reason=="INSUFFICIENT_COMPLETED_1H_BARS" and sparse.atr_15m_reason=="INSUFFICIENT_COMPLETED_15M_BARS"
    print("8. insufficient history handled explicitly: PASS")
    miss=svc.evaluate(as_of=datetime(2026,9,15,10,0,tzinfo=ET),trading_date_et=date(2026,9,15),calendar=sessions,minute_bars=mins)
    assert miss.atr_1h is None and miss.atr_15m is None
    assert miss.atr_1h_reason=="CURRENT_SESSION_NOT_FOUND" and miss.atr_15m_reason=="CURRENT_SESSION_NOT_FOUND"
    print("9. missing current session handled: PASS")
    raised=False
    try:
        svc.evaluate(as_of=datetime(2026,9,14,10,0),trading_date_et=date(2026,9,14),calendar=sessions,minute_bars=mins)
    except ATRError:
        raised=True
    assert raised
    print("10. naive as_of rejected: PASS")
    print("\n"+"="*70); print("ATR SERVICE: PASS 10/10"); print("="*70)

if __name__=="__main__": main()
