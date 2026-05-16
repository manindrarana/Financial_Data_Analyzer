"""Quick test to inspect raw Bybit API response for Open Interest and Funding Rate"""
import os
import json
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()
api_key = os.getenv("BYBIT_API_KEY")
api_secret = os.getenv("BYBIT_API_SECRET")

session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

symbol = "BTCUSDT"

print("=" * 60)
print("1. OPEN INTEREST (1h)")
print("=" * 60)
oi_response = session.get_open_interest(
    category="linear",
    symbol=symbol,
    intervalTime="1h",
    limit=5
)
print(f"Full response keys: {list(oi_response.keys())}")
print(f"retCode: {oi_response.get('retCode')}")
print(f"retMsg: {oi_response.get('retMsg')}")
raw_list = oi_response.get('result', {}).get('list', [])
print(f"List length: {len(raw_list)}")
if raw_list:
    print(f"Type of first item: {type(raw_list[0])}")
    print(f"First item: {json.dumps(raw_list[0], indent=2)}")
    if isinstance(raw_list[0], dict):
        print(f"Keys: {list(raw_list[0].keys())}")
        print(f"Has 'timestamp': {'timestamp' in raw_list[0]}")
        print(f"Has 'openInterest': {'openInterest' in raw_list[0]}")
        print(f"Has 'openInterestValue': {'openInterestValue' in raw_list[0]}")
    elif isinstance(raw_list[0], list):
        print(f"Length: {len(raw_list[0])}")
else:
    print(f"Full result: {json.dumps(oi_response.get('result'), indent=2)}")

print()
print("=" * 60)
print("2. FUNDING RATE HISTORY")
print("=" * 60)
fr_response = session.get_funding_rate_history(
    category="linear",
    symbol=symbol,
    limit=5
)
print(f"Full response keys: {list(fr_response.keys())}")
print(f"retCode: {fr_response.get('retCode')}")
print(f"retMsg: {fr_response.get('retMsg')}")
raw_list = fr_response.get('result', {}).get('list', [])
print(f"List length: {len(raw_list)}")
if raw_list:
    print(f"Type of first item: {type(raw_list[0])}")
    print(f"First item: {json.dumps(raw_list[0], indent=2)}")
    if isinstance(raw_list[0], dict):
        print(f"Keys: {list(raw_list[0].keys())}")
        print(f"Has 'timestamp': {'timestamp' in raw_list[0]}")
        print(f"Has 'fundingRate': {'fundingRate' in raw_list[0]}")
        print(f"Has 'fundingRateTimestamp': {'fundingRateTimestamp' in raw_list[0]}")
    elif isinstance(raw_list[0], list):
        print(f"Length: {len(raw_list[0])}")

print()
print("=" * 60)
print("3. KLINE RESPONSE (to verify list item format)")
print("=" * 60)
kline_response = session.get_kline(
    category="linear",
    symbol=symbol,
    interval="60",
    limit=3
)
raw_list = kline_response.get('result', {}).get('list', [])
if raw_list:
    print(f"Type of first kline item: {type(raw_list[0])}")
    print(f"First kline item: {json.dumps(raw_list[0], indent=2)}")
    if isinstance(raw_list[0], list):
        print(f"Kline is an ARRAY (positional access works)")
        print(f"Length: {len(raw_list[0])}")
    elif isinstance(raw_list[0], dict):
        print(f"Kline is a DICT (key access works)")
        print(f"Keys: {list(raw_list[0].keys())}")

session.close()