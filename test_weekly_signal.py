from dotenv import load_dotenv
import os
import requests
from datetime import date, timedelta

load_dotenv()

uw_key = os.getenv("UW_API_KEY")
headers = {"Authorization": f"Bearer {uw_key}", "Accept": "application/json"}

tickers = ["AAPL", "TSLA", "NVDA", "GOOGL", "META"]
FLOW_THRESHOLD = 500000


def get_next_friday():
    today = date.today()
    days_until_friday = (4 - today.weekday()) % 7

    if days_until_friday == 0:
        days_until_friday = 7

    next_friday = today + timedelta(days=days_until_friday)
    return next_friday.isoformat()


def get_weekly_signal(ticker, valid_expiry):
    url = f"https://api.unusualwhales.com/api/stock/{ticker}/flow-alerts"
    params = {"limit": 200}
    response = requests.get(url, headers=headers, params=params, timeout=15)

    if response.status_code != 200:
        print(f"خطأ Unusual Whales لـ{ticker}: كود {response.status_code}")
        return None, 0, 0, 0

    alerts = response.json().get("data", [])

    calls_prem = 0.0
    puts_prem = 0.0
    sweep_prem = 0.0
    opening_count = 0
    total_matched = 0
    duplicates_skipped = 0

    processed_alert_ids = set()

    for alert in alerts:
        expiry = alert.get("expiry")
        if expiry != valid_expiry:
            continue

        if alert.get("has_multileg"):
            continue
        if not alert.get("has_singleleg"):
            continue

        # مفتاح تركيبي فريد (ما فيه id رسمي بالبيانات الفعلية)
        composite_key = f"{alert.get('created_at')}|{alert.get('option_chain')}|{alert.get('alert_rule')}"
        if composite_key in processed_alert_ids:
            duplicates_skipped += 1
            continue
        processed_alert_ids.add(composite_key)

        ask_prem = float(alert.get("total_ask_side_prem", 0))
        if ask_prem <= 0:
            continue

        total_matched += 1

        if alert.get("type") == "call":
            calls_prem += ask_prem
        elif alert.get("type") == "put":
            puts_prem += ask_prem

        if alert.get("has_sweep"):
            sweep_prem += ask_prem

        if alert.get("all_opening_trades"):
            opening_count += 1

    net_flow = calls_prem - puts_prem
    sweep_ratio = (sweep_prem / (calls_prem + puts_prem) * 100) if (calls_prem + puts_prem) > 0 else 0

    print(f"--- {ticker} (تاريخ الانتهاء المستهدف: {valid_expiry}) ---")
    print(f"  عدد الصفقات المطابقة (single-leg بس): {total_matched}")
    print(f"  مكررات تم تجاهلها: {duplicates_skipped}")
    print(f"  Calls: ${calls_prem:,.0f}  |  Puts: ${puts_prem:,.0f}")
    print(f"  صافي التدفق: ${net_flow:,.0f}")
    print(f"  نسبة Sweeps: {sweep_ratio:.1f}%")
    print(f"  عدد الصفقات اللي فتحت مراكز جديدة بالكامل: {opening_count}")

    if net_flow > FLOW_THRESHOLD:
        return "buy", net_flow, sweep_ratio, opening_count
    elif net_flow < -FLOW_THRESHOLD:
        return "sell", net_flow, sweep_ratio, opening_count
    else:
        return None, net_flow, sweep_ratio, opening_count


valid_expiry = get_next_friday()
print(f"أقرب جمعة صالحة: {valid_expiry}\n")

for ticker in tickers:
    signal_type, net_flow, sweep_ratio, opening_count = get_weekly_signal(ticker, valid_expiry)
    if signal_type:
        print(f"  >>> إشارة: {signal_type}\n")
    else:
        print(f"  >>> لا توجد إشارة\n")