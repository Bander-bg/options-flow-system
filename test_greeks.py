from dotenv import load_dotenv
import os
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest

load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")

option_client = OptionHistoricalDataClient(api_key, secret_key)
request = OptionChainRequest(underlying_symbol="META")
chain = option_client.get_option_chain(request)

count = 0
for symbol, snapshot in chain.items():
    print(symbol)
    print("  Delta:", snapshot.greeks.delta if snapshot.greeks else "غير متوفر")
    print("  Theta:", snapshot.greeks.theta if snapshot.greeks else "غير متوفر")
    print("  Gamma:", snapshot.greeks.gamma if snapshot.greeks else "غير متوفر")
    count += 1
    if count >= 5:
        break