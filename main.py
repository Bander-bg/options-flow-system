from dotenv import load_dotenv
import os
import requests
import time
import json
import math
from datetime import date, timedelta, datetime
from alpaca.trading.client import TradingClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest, StockLatestTradeRequest, OptionLatestQuoteRequest, StockBarsRequest
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.timeframe import TimeFrame

load_dotenv()

alpaca_key = os.getenv("ALPACA_API_KEY")
alpaca_secret = os.getenv("ALPACA_SECRET_KEY")
uw_key = os.getenv("UW_API_KEY")
tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

tickers = ["AAPL", "TSLA", "NVDA", "GOOGL", "META"]
FLOW_THRESHOLD = 500000
MAX_SPREAD_PERCENT = 15.0
MONEYNESS_RANGE_PERCENT = 5.0
MAX_BUDGET = 1000.0

BUTTON_CHECK_INTERVAL_SECONDS = 10
POSITION_CHECK_INTERVAL_SECONDS = 60
SIGNAL_SCAN_INTERVAL_SECONDS = 300

POSITIONS_FILE = "open_positions.json"
DAILY_STATE_FILE = "daily_state.json"

STOP_LOSS_PERCENT = 20.0
TRAILING_ACTIVATION_PROFIT_PERCENT = 50.0
TRAILING_GIVEBACK_PERCENT = 20.0
EOD_MINUTES_BEFORE_CLOSE = 60
PREMARKET_MINUTES_BEFORE_OPEN = 30

MAX_OPEN_POSITIONS = 5
DAILY_LOSS_LIMIT = 100.0

GAMMA_MIN = 0.005
GAMMA_MAX = 0.05

EFFICIENCY_MIN_THRESHOLD = 0.3

GRADE_A_SCORE = 4.0
GRADE_B_SCORE = 2.0

trading_client = TradingClient(alpaca_key, alpaca_secret, paper=True)
stock_client = StockHistoricalDataClient(alpaca_key, alpaca_secret)
option_client = OptionHistoricalDataClient(alpaca_key, alpaca_secret)

last_update_id = 0


def get_next_valid_expiries(n=2):
    dates = []
    d = date.today()
    while len(dates) < n:
        if d.weekday() in (0, 2, 4):
            dates.append(d.isoformat())
        d += timedelta(days=1)
    return dates


def get_market_reading(ticker):
    try:
        clock = trading_client.get_clock()
        now = clock.timestamp
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        request = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Minute, start=today_start, end=now)
        bars = stock_client.get_stock_bars(request)
        bar_list = bars[ticker]

        if not bar_list or len(bar_list) < 5:
            return None, 0, None, None

        cum_pv = 0.0
        cum_vol = 0.0
        closes = []
        for bar in bar_list:
            typical_price = (bar.high + bar.low + bar.close) / 3
            cum_pv += typical_price * bar.volume
            cum_vol += bar.volume
            closes.append(bar.close)

        if cum_vol == 0:
            return None, 0, None, None

        vwap = cum_pv / cum_vol
        last_price = closes[-1]
        distance_percent = ((last_price - vwap) / vwap) * 100
        trend = "up" if last_price > vwap else "down"

        net_move = abs(closes[-1] - closes[0])
        total_move = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
        efficiency_ratio = (net_move / total_move) if total_move > 0 else 0

        return trend, distance_percent, vwap, efficiency_ratio
    except Exception as e:
        print(f"خطأ بحساب قراءة السوق لـ{ticker}: {e}")
        return None, 0, None, None


def get_signal(ticker):
    try:
        url = f"https://api.unusualwhales.com/api/stock/{ticker}/flow-alerts"
        headers = {"Authorization": f"Bearer {uw_key}", "Accept": "application/json"}
        params = {"limit": 200}
        response = requests.get(url, headers=headers, params=params, timeout=15)

        if response.status_code != 200:
            print(f"خطأ Unusual Whales لـ{ticker}: كود {response.status_code} - {response.text[:200]}")
            return None, 0

        alerts = response.json().get("data", [])
    except Exception as e:
        print(f"خطأ اتصال بجلب إشارة {ticker}: {e}")
        return None, 0

    valid_expiries = get_next_valid_expiries()
    calls_prem = 0.0
    puts_prem = 0.0

    for alert in alerts:
        ask_prem = float(alert.get("total_ask_side_prem", 0))
        expiry = alert.get("expiry")
        if ask_prem > 0 and expiry in valid_expiries:
            if alert.get("type") == "call":
                calls_prem += ask_prem
            elif alert.get("type") == "put":
                puts_prem += ask_prem

    net_flow = calls_prem - puts_prem

    if net_flow > FLOW_THRESHOLD:
        return "buy", net_flow
    elif net_flow < -FLOW_THRESHOLD:
        return "sell", net_flow
    else:
        return None, net_flow


def get_gex_status(ticker):
    try:
        url = f"https://api.unusualwhales.com/api/stock/{ticker}/greek-exposure"
        headers = {"Authorization": f"Bearer {uw_key}", "Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            return "غير متوفر"

        data = response.json().get("data", [])
    except Exception:
        return "غير متوفر"

    if not data:
        return "غير متوفر"

    latest = data[0]
    call_gamma = float(latest.get("call_gamma", 0))
    put_gamma = float(latest.get("put_gamma", 0))
    net_gamma = call_gamma + put_gamma

    if net_gamma > 0:
        return "إيجابي (صناع السوق يميلون لتهدئة الحركة)"
    else:
        return "سلبي (صناع السوق يميلون لتضخيم الحركة)"


def select_contract(ticker, signal_type):
    try:
        valid_expiries = get_next_valid_expiries()

        stock_request = StockLatestTradeRequest(symbol_or_symbols=ticker)
        underlying_price = float(stock_client.get_stock_latest_trade(stock_request)[ticker].price)

        price_min = underlying_price * (1 - MONEYNESS_RANGE_PERCENT / 100)
        price_max = underlying_price * (1 + MONEYNESS_RANGE_PERCENT / 100)

        request = OptionChainRequest(underlying_symbol=ticker)
        chain = option_client.get_option_chain(request)
    except Exception as e:
        print(f"خطأ بجلب بيانات العقود لـ{ticker}: {e}")
        return None

    candidates = []

    for symbol, snapshot in chain.items():
        expiry = symbol[len(ticker):len(ticker)+6]
        expiry_formatted = "20" + expiry[0:2] + "-" + expiry[2:4] + "-" + expiry[4:6]
        if expiry_formatted not in valid_expiries:
            continue

        option_flag = symbol[len(ticker)+6]
        option_kind = "call" if option_flag == "C" else "put"
        if signal_type == "buy" and option_kind != "call":
            continue
        if signal_type == "sell" and option_kind != "put":
            continue

        strike = float(symbol[len(ticker)+7:]) / 1000
        if strike < price_min or strike > price_max:
            continue

        if not snapshot.greeks:
            continue

        delta = snapshot.greeks.delta
        theta = snapshot.greeks.theta
        gamma = snapshot.greeks.gamma
        if theta == 0:
            continue

        if gamma < GAMMA_MIN or gamma > GAMMA_MAX:
            continue

        ratio = abs(delta) / abs(theta)

        quote = snapshot.latest_quote
        if not quote or quote.ask_price == 0:
            continue

        mid_price = round((quote.bid_price + quote.ask_price) / 2, 2)
        spread_percent = ((quote.ask_price - quote.bid_price) / mid_price) * 100
        if spread_percent > MAX_SPREAD_PERCENT:
            continue

        contract_cost = quote.ask_price * 100
        if contract_cost > MAX_BUDGET:
            continue

        expiry_date = date.fromisoformat(expiry_formatted)
        days_to_expiry = max((expiry_date - date.today()).days, 1)
        iv = snapshot.implied_volatility if snapshot.implied_volatility else 0

        expected_move = underlying_price * iv * math.sqrt(days_to_expiry / 365)
        range_low = underlying_price - expected_move
        range_high = underlying_price + expected_move

        candidates.append({
            "symbol": symbol, "strike": strike, "delta": delta, "theta": theta,
            "gamma": gamma, "ratio": ratio, "spread_percent": spread_percent,
            "contract_cost": contract_cost,
            "ask_price": quote.ask_price, "bid_price": quote.bid_price, "mid_price": mid_price,
            "expiry_formatted": expiry_formatted,
            "underlying_price": underlying_price,
            "range_low": range_low, "range_high": range_high,
            "option_kind": option_kind
        })

    if not candidates:
        return None

    return max(candidates, key=lambda c: c["ratio"])


def get_current_option_price(symbol):
    try:
        request = OptionLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = option_client.get_option_latest_quote(request)[symbol]
        if quote.bid_price == 0 or quote.ask_price == 0:
            print(f"  [تشخيص] سعر {symbol} صفر (bid={quote.bid_price}, ask={quote.ask_price})")
            return None
        return (quote.bid_price + quote.ask_price) / 2
    except Exception as e:
        print(f"خطأ بجلب سعر {symbol}: {e}")
        return None


def send_telegram_with_buttons(text, button_text, callback_data):
    try:
        url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
        keyboard = {
            "inline_keyboard": [[
                {"text": button_text, "callback_data": callback_data},
                {"text": "❌ تجاهل", "callback_data": "ignore"}
            ]]
        }
        data = {"chat_id": tg_chat_id, "text": text, "reply_markup": json.dumps(keyboard)}
        r = requests.post(url, data=data, timeout=15)
        print(f"  [تشخيص] إرسال رسالة تيليجرام: كود {r.status_code}")
    except Exception as e:
        print(f"خطأ إرسال تيليجرام: {e}")


def send_telegram_plain(text):
    try:
        url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
        r = requests.post(url, data={"chat_id": tg_chat_id, "text": text}, timeout=15)
        print(f"  [تشخيص] إرسال رسالة تيليجرام بسيطة: كود {r.status_code}")
    except Exception as e:
        print(f"خطأ إرسال تيليجرام: {e}")


def load_positions():
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_positions(positions):
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)


def load_daily_state():
    today = date.today().isoformat()
    if os.path.exists(DAILY_STATE_FILE):
        with open(DAILY_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        if state.get("date") == today:
            if "alerted_tickers" not in state:
                state["alerted_tickers"] = []
            return state
    return {
        "date": today,
        "cumulative_loss": 0.0,
        "breaker_notified": False,
        "market_opened_today": False,
        "summary_sent": False,
        "premarket_notified": False,
        "closed_trades": [],
        "signals_sent_count": 0,
        "alerted_tickers": []
    }


def save_daily_state(state):
    with open(DAILY_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def archive_daily_state(state):
    os.makedirs("history", exist_ok=True)
    filepath = f"history/{state['date']}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_daily_summary(daily_state):
    trades = daily_state.get("closed_trades", [])
    signals_count = daily_state.get("signals_sent_count", 0)

    if not trades and signals_count == 0:
        send_telegram_plain(f"📅 ملخص يوم {daily_state['date']}\n\nما صدرت أي إشارات اليوم.")
        return

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in trades)

    lines = [f"📅 ملخص يوم {daily_state['date']}\n"]
    lines.append(f"عدد الإشارات المرسلة: {signals_count}")
    lines.append(f"عدد الصفقات المغلقة: {len(trades)}")
    lines.append(f"رابحة: {len(wins)} | خاسرة: {len(losses)}")
    lines.append(f"صافي الربح/الخسارة لليوم: ${total_pnl:.2f}")

    if trades:
        lines.append("\nتفاصيل الصفقات:")
        for t in trades:
            result = "✅ ربح" if t["pnl"] > 0 else "❌ خسارة"
            ticker_name = t['symbol']
            for tk in tickers:
                if t['symbol'].startswith(tk):
                    ticker_name = tk
                    break
            lines.append(f"{ticker_name}: {result} ${t['pnl']:.2f}")

    send_telegram_plain("\n".join(lines))


def check_telegram_buttons():
    global last_update_id
    try:
        url = f"https://api.telegram.org/bot{tg_token}/getUpdates"
        params = {"offset": last_update_id + 1, "timeout": 1}
        response = requests.get(url, params=params, timeout=15).json()
    except Exception as e:
        print(f"خطأ بجلب تحديثات تيليجرام: {e}")
        return

    updates_count = len(response.get("result", []))
    if updates_count > 0:
        print(f"  [تشخيص] وصلت {updates_count} تحديثات من تيليجرام")

    positions = load_positions()
    daily_state = load_daily_state()

    for update in response.get("result", []):
        last_update_id = update["update_id"]

        callback = update.get("callback_query")
        if not callback:
            continue

        data = callback.get("data", "")
        callback_id = callback["id"]
        print(f"  [تشخيص] ضغطة زر مستلمة: {data}")

        answer_url = f"https://api.telegram.org/bot{tg_token}/answerCallbackQuery"
        try:
            requests.post(answer_url, data={"callback_query_id": callback_id}, timeout=15)
        except Exception:
            pass

        if data.startswith("enter:"):
            _, symbol = data.split(":")
            live_price = get_current_option_price(symbol)
            if live_price is None:
                print(f"  [تشخيص] فشل جلب سعر حي لـ{symbol} عند الدخول")
                send_telegram_plain(f"⚠️ ما قدرنا نجيب سعر حي لـ{symbol} الآن، حاول تضغط الزر مرة ثانية")
                continue

            positions.append({
                "symbol": symbol,
                "entry_price": live_price,
                "entry_time": datetime.now().isoformat(),
                "peak_price": live_price,
                "exit_alert_sent": False,
                "exit_reason": None
            })
            save_positions(positions)
            print(f"  [تشخيص] تم تسجيل صفقة جديدة: {symbol} بسعر {live_price}")
            send_telegram_plain(f"✅ تم تسجيل دخولك على {symbol} بسعر السوق الحي: ${live_price:.2f}")

        elif data.startswith("exit:"):
            _, symbol = data.split(":")
            live_price = get_current_option_price(symbol)

            matching = [p for p in positions if p["symbol"] == symbol]
            if not matching:
                print(f"  [تشخيص] ضغطة خروج لـ{symbol} بس ما لقيته بقائمة الصفقات المفتوحة")
                continue
            pos = matching[0]

            if live_price is not None:
                pnl_dollars = (live_price - pos["entry_price"]) * 100
                if pnl_dollars < 0:
                    daily_state["cumulative_loss"] += abs(pnl_dollars)
                daily_state["closed_trades"].append({"symbol": symbol, "pnl": pnl_dollars})

                for tk in tickers:
                    if symbol.startswith(tk) and tk in daily_state["alerted_tickers"]:
                        daily_state["alerted_tickers"].remove(tk)

                save_daily_state(daily_state)
                print(f"  [تشخيص] تم إغلاق {symbol} بربح/خسارة {pnl_dollars:.2f}")
                send_telegram_plain(
                    f"✅ تم إغلاق {symbol}\n"
                    f"سعر الدخول: ${pos['entry_price']:.2f} | سعر الخروج الفعلي: ${live_price:.2f}\n"
                    f"الربح/الخسارة: ${pnl_dollars:.2f}"
                )
            else:
                print(f"  [تشخيص] فشل جلب سعر حي لـ{symbol} عند الخروج")
                send_telegram_plain(f"✅ تم إغلاق {symbol} من المراقبة (ما قدرنا نجيب سعر حي لحساب الربح/الخسارة)")

            positions = [p for p in positions if p["symbol"] != symbol]
            save_positions(positions)


def monitor_positions():
    positions = load_positions()
    if not positions:
        return

    print(f"  [تشخيص] مراقبة {len(positions)} صفقة مفتوحة: {[p['symbol'] for p in positions]}")

    clock = trading_client.get_clock()
    minutes_to_close = (clock.next_close - clock.timestamp).total_seconds() / 60

    changed = False

    for pos in positions:
        if pos.get("exit_alert_sent"):
            print(f"  [تشخيص] {pos['symbol']}: تنبيه خروج أُرسل سابقاً، بانتظار ضغطتك على الزر")
            continue

        current_price = get_current_option_price(pos["symbol"])
        if current_price is None:
            print(f"  [تشخيص] {pos['symbol']}: ما قدرنا نجيب سعره الحي هالدورة")
            continue

        if current_price > pos["peak_price"]:
            pos["peak_price"] = current_price
            changed = True

        entry = pos["entry_price"]
        peak = pos["peak_price"]

        pnl_percent = ((current_price - entry) / entry) * 100
        peak_profit_percent = ((peak - entry) / entry) * 100

        print(f"  [تشخيص] {pos['symbol']}: دخول={entry:.2f} حالي={current_price:.2f} قمة={peak:.2f} ربح_حالي={pnl_percent:.1f}% ربح_القمة={peak_profit_percent:.1f}%")

        exit_reason = None

        if peak_profit_percent >= TRAILING_ACTIVATION_PROFIT_PERCENT:
            peak_profit = peak - entry
            trailing_stop_price = peak - (TRAILING_GIVEBACK_PERCENT / 100) * peak_profit

            if current_price <= trailing_stop_price:
                exit_reason = f"وقف ربح متحرك (تجاوزت 50% ربح ثم تراجعت 20% من الذروة — وقف الخروج عند ${trailing_stop_price:.2f})"
        else:
            if current_price <= entry * (1 - STOP_LOSS_PERCENT / 100):
                exit_reason = "وقف خسارة ثابت (نزل 20% من سعر الدخول، ولم تصل الصفقة 50% ربح بعد)"

        if not exit_reason and minutes_to_close <= EOD_MINUTES_BEFORE_CLOSE and current_price <= entry:
            exit_reason = "إغلاق نهاية اليوم (باقي أقل من ساعة على إغلاق السوق ولا يوجد ربح)"

        if exit_reason:
            pos["exit_alert_sent"] = True
            pos["exit_reason"] = exit_reason
            changed = True
            print(f"  [تشخيص] {pos['symbol']}: تحقق شرط خروج -> {exit_reason}")

            message = (
                f"🔔 تنبيه خروج: {pos['symbol']}\n\n"
                f"السبب: {exit_reason}\n"
                f"سعر الدخول: ${entry:.2f}\n"
                f"أعلى سعر وصلته الصفقة (الذروة): ${peak:.2f}\n"
                f"السعر وقت التنبيه: ${current_price:.2f} (تقريبي، الاحتساب الفعلي وقت ضغطك على الزر)\n"
                f"نسبة الربح/الخسارة التقريبية: {pnl_percent:.1f}%\n\n"
                f"نفّذ البيع يدوياً بدراية، وبعدها اضغط الزر بالأسفل — بنسجل سعر الخروج الفعلي وقت ضغطتك."
            )
            send_telegram_with_buttons(message, "✅ خرجت", f"exit:{pos['symbol']}")

    if changed:
        save_positions(positions)


def get_tickers_with_open_positions(positions):
    open_tickers = set()
    for pos in positions:
        for ticker in tickers:
            if pos["symbol"].startswith(ticker):
                open_tickers.add(ticker)
    return open_tickers


def calculate_grade(net_flow, trend_distance_percent, efficiency_ratio):
    flow_ratio = abs(net_flow) / FLOW_THRESHOLD
    score = flow_ratio + (abs(trend_distance_percent) / 2) + (efficiency_ratio * 3)

    if score >= GRADE_A_SCORE:
        return "A", score
    elif score >= GRADE_B_SCORE:
        return "B", score
    else:
        return "C", score


def run_scan():
    positions = load_positions()
    daily_state = load_daily_state()

    if daily_state["cumulative_loss"] >= DAILY_LOSS_LIMIT:
        if not daily_state["breaker_notified"]:
            send_telegram_plain(f"🛑 تم إيقاف إرسال إشارات جديدة لبقية اليوم — تجاوزت الخسارة اليومية ${DAILY_LOSS_LIMIT:.0f}")
            daily_state["breaker_notified"] = True
            save_daily_state(daily_state)
        return

    log_file = "signals_log.txt"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n===== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

        for ticker in tickers:
            positions = load_positions()
            open_tickers = get_tickers_with_open_positions(positions)
            daily_state = load_daily_state()

            if ticker in open_tickers:
                line = f"{ticker}: يوجد صفقة مفتوحة عليه بالفعل، تم تخطي فحص إشارة جديدة"
                print(line)
                f.write(line + "\n")
                continue

            if ticker in daily_state.get("alerted_tickers", []):
                line = f"{ticker}: سبق إرسال تنبيه له اليوم وما دخلتها/أغلقتها بعد، تم تخطي فحص إشارة جديدة"
                print(line)
                f.write(line + "\n")
                continue

            signal_type, net_flow = get_signal(ticker)
            line = f"{ticker}: صافي التدفق=${net_flow:,.0f}"

            if signal_type is None:
                line += " -> لا توجد إشارة"
                print(line)
                f.write(line + "\n")
                continue

            signal_label = "شراء" if signal_type == "buy" else "بيع"
            line += f" -> إشارة {signal_label}"
            print(line)
            f.write(line + "\n")

            trend, trend_distance, vwap_value, efficiency_ratio = get_market_reading(ticker)

            if trend is not None:
                if signal_type == "buy" and trend == "down":
                    msg = f"⛔ إشارة شراء على {ticker} لكن السعر تحت VWAP اليوم ({trend_distance:.2f}%) — تم تجاهلها لتعارضها مع زخم اليوم"
                    print(msg)
                    f.write(msg + "\n")
                    continue
                if signal_type == "sell" and trend == "up":
                    msg = f"⛔ إشارة بيع على {ticker} لكن السعر فوق VWAP اليوم ({trend_distance:.2f}%) — تم تجاهلها لتعارضها مع زخم اليوم"
                    print(msg)
                    f.write(msg + "\n")
                    continue

            if efficiency_ratio is not None and efficiency_ratio < EFFICIENCY_MIN_THRESHOLD:
                msg = f"⛔ إشارة {signal_label} على {ticker} لكن السهم بمنطقة عرضية اليوم (كفاءة الاتجاه {efficiency_ratio:.2f} أقل من {EFFICIENCY_MIN_THRESHOLD}) — تم تجاهلها لتجنب التذبذب"
                print(msg)
                f.write(msg + "\n")
                continue

            if len(positions) >= MAX_OPEN_POSITIONS:
                msg = f"⚠️ إشارة {signal_label} على {ticker} لكن وصلنا الحد الأقصى ({MAX_OPEN_POSITIONS}) من الصفقات المفتوحة، تم تجاهلها"
                print(msg)
                f.write(msg + "\n")
                continue

            contract = select_contract(ticker, signal_type)

            if contract is None:
                msg = f"⚠️ إشارة {signal_label} على {ticker} لكن ما فيه عقد مناسب ضمن الشروط"
                print(msg)
                f.write(msg + "\n")
                send_telegram_plain(msg)
                continue

            approx_probability = abs(contract['delta']) * 100
            gex_status = get_gex_status(ticker)
            option_kind_label = "Call (كول) — عقد شراء" if contract['option_kind'] == "call" else "Put (بوت) — عقد بيع"

            grade, score = calculate_grade(
                net_flow,
                trend_distance if trend is not None else 0,
                efficiency_ratio if efficiency_ratio is not None else 0
            )
            trend_label = "فوق VWAP (زخم صاعد)" if trend == "up" else ("تحت VWAP (زخم هابط)" if trend == "down" else "غير متوفر")
            grade_emoji = {"A": "🟢", "B": "🟡", "C": "🟠"}[grade]
            efficiency_display = f"{efficiency_ratio:.2f}" if efficiency_ratio is not None else "غير متوفر"

            message = (
                f"📊 إشارة {signal_label} على {ticker}\n"
                f"🏷️ نوع العقد: {option_kind_label}\n"
                f"{grade_emoji} تقييم جودة الصفقة: {grade}\n\n"
                f"📈 زخم السهم اليوم: {trend_label}"
                + (f" ({trend_distance:.2f}% عن VWAP)" if trend is not None else "") + "\n"
                f"📐 كفاءة الاتجاه (Efficiency Ratio): {efficiency_display} (أعلى من {EFFICIENCY_MIN_THRESHOLD} = بعيد عن المنطقة العرضية)\n"
                f"💰 Bid: ${contract['bid_price']:.2f} | Ask: ${contract['ask_price']:.2f} | المتوسط (سعر الدخول المقترح): ${contract['mid_price']:.2f}\n"
                f"📅 تاريخ الانتهاء: {contract['expiry_formatted']}\n"
                f"🎯 سعر التنفيذ (Strike): {contract['strike']}\n"
                f"📈 احتمال تقريبي ينتهي بربح (مبني على Delta، ليس ضماناً): {approx_probability:.0f}%\n"
                f"📊 المدى المتوقع لحركة سعر {ticker} حتى الانتهاء: من ${contract['range_low']:.2f} إلى ${contract['range_high']:.2f} (السعر الحالي: ${contract['underlying_price']:.2f})\n"
                f"⚖️ وضع صناع السوق (GEX): {gex_status}\n\n"
                f"صافي التدفق: ${net_flow:,.0f}\n"
                f"Delta: {contract['delta']:.3f}\n"
                f"Theta: {contract['theta']:.3f}\n"
                f"Gamma: {contract['gamma']:.4f}\n"
                f"السبريد: {contract['spread_percent']:.1f}%\n\n"
                f"(سعر دخولك الفعلي بيُسجل تلقائياً وقت ضغطك على الزر بالأسفل)"
            )
            print(message)
            f.write(message + "\n")
            send_telegram_with_buttons(message, "✅ دخلت الصفقة", f"enter:{contract['symbol']}")

            daily_state = load_daily_state()
            daily_state["signals_sent_count"] += 1
            daily_state["alerted_tickers"].append(ticker)
            save_daily_state(daily_state)


print("النظام بدأ المراقبة... (اضغط Ctrl+C لإيقافه)")

last_position_check = 0
last_signal_scan = 0

while True:
    check_telegram_buttons()

    now_ts = time.time()
    clock = trading_client.get_clock()
    daily_state = load_daily_state()

    if clock.is_open:
        if not daily_state["market_opened_today"]:
            daily_state["market_opened_today"] = True
            save_daily_state(daily_state)

        if now_ts - last_position_check >= POSITION_CHECK_INTERVAL_SECONDS:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] مراقبة الصفقات المفتوحة...")
            monitor_positions()
            last_position_check = now_ts

        if now_ts - last_signal_scan >= SIGNAL_SCAN_INTERVAL_SECONDS:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] فحص إشارات جديدة...")
            run_scan()
            last_signal_scan = now_ts
    else:
        if daily_state["market_opened_today"] and not daily_state["summary_sent"]:
            send_daily_summary(daily_state)
            archive_daily_state(daily_state)
            daily_state["summary_sent"] = True
            save_daily_state(daily_state)

        minutes_to_open = (clock.next_open - clock.timestamp).total_seconds() / 60
        if not daily_state["premarket_notified"] and minutes_to_open <= PREMARKET_MINUTES_BEFORE_OPEN:
            send_telegram_plain(
                f"🔔 السوق يفتح خلال أقل من {PREMARKET_MINUTES_BEFORE_OPEN} دقيقة — النظام جاهز ومراقب."
            )
            daily_state["premarket_notified"] = True
            save_daily_state(daily_state)

    time.sleep(BUTTON_CHECK_INTERVAL_SECONDS)