from dotenv import load_dotenv
import os
import requests

load_dotenv()

uw_key = os.getenv("UW_API_KEY")
headers = {"Authorization": f"Bearer {uw_key}", "Accept": "application/json"}

ticker = "AAPL"

print(f"--- اختبار 1: greek-exposure/strike لـ {ticker} ---")
url1 = f"https://api.unusualwhales.com/api/stock/{ticker}/greek-exposure/strike"
response1 = requests.get(url1, headers=headers)
print(f"كود الحالة: {response1.status_code}")
print(f"أول جزء من الرد: {response1.text[:500]}")

print(f"\n--- اختبار 2: spot-exposures/strike لـ {ticker} ---")
url2 = f"https://api.unusualwhales.com/api/stock/{ticker}/spot-exposures/strike"
response2 = requests.get(url2, headers=headers)
print(f"كود الحالة: {response2.status_code}")
print(f"أول جزء من الرد: {response2.text[:500]}")

print(f"\n--- اختبار 3: interpolated-iv لـ {ticker} (للتحقق من IV Percentile كمان) ---")
url3 = f"https://api.unusualwhales.com/api/stock/{ticker}/interpolated-iv"
response3 = requests.get(url3, headers=headers)
print(f"كود الحالة: {response3.status_code}")
print(f"أول جزء من الرد: {response3.text[:500]}")