#!/usr/bin/env python3
"""
Test script for crypto markets
"""

from crypto_polymarket_api import CryptoPolymarketAPI
from crypto_kalshi_api import CryptoKalshiAPI
import json

def test_crypto_apis():
    print("=" * 60)
    print("Testing Crypto Market APIs")
    print("=" * 60)
    
    # Test Polymarket
    print("\n1. Testing Polymarket Crypto API...")
    try:
        poly_api = CryptoPolymarketAPI()
        poly_markets = poly_api.get_crypto_markets(limit=10)
        print(f"   ✓ Found {len(poly_markets)} Polymarket crypto markets")
        if poly_markets:
            sample = poly_markets[0]
            print(f"   Sample market:")
            print(f"   - Question: {sample.get('question', 'N/A')}")
            print(f"   - Away: {sample.get('away_team', 'N/A')}")
            print(f"   - Home: {sample.get('home_team', 'N/A')}")
            print(f"   - Away Code: {sample.get('away_code', 'N/A')}")
            print(f"   - Home Code: {sample.get('home_code', 'N/A')}")
            print(f"   - Normalized Key: {sample.get('normalized_key', 'N/A')}")
            print(f"   - Away Prob: {sample.get('away_prob', 0)}%")
            print(f"   - Home Prob: {sample.get('home_prob', 0)}%")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test Kalshi
    print("\n2. Testing Kalshi Crypto API...")
    try:
        kalshi_api = CryptoKalshiAPI()
        kalshi_markets = kalshi_api.get_crypto_markets(limit=10)
        print(f"   ✓ Found {len(kalshi_markets)} Kalshi crypto markets")
        if kalshi_markets:
            sample = kalshi_markets[0]
            print(f"   Sample market:")
            print(f"   - Question: {sample.get('question', 'N/A')}")
            print(f"   - Away: {sample.get('away_team', 'N/A')}")
            print(f"   - Home: {sample.get('home_team', 'N/A')}")
            print(f"   - Away Code: {sample.get('away_code', 'N/A')}")
            print(f"   - Home Code: {sample.get('home_code', 'N/A')}")
            print(f"   - Normalized Key: {sample.get('normalized_key', 'N/A')}")
            print(f"   - Away Prob: {sample.get('away_prob', 0)}%")
            print(f"   - Home Prob: {sample.get('home_prob', 0)}%")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Check for potential matches
    print("\n3. Checking for potential cross-platform matches...")
    try:
        poly_keys = {m.get('normalized_key'): m for m in poly_markets if m.get('normalized_key')}
        kalshi_keys = {m.get('normalized_key'): m for m in kalshi_markets if m.get('normalized_key')}
        
        common_keys = set(poly_keys.keys()) & set(kalshi_keys.keys())
        
        if common_keys:
            print(f"   ✓ Found {len(common_keys)} potential matches!")
            for key in list(common_keys)[:3]:  # Show first 3 matches
                poly_m = poly_keys[key]
                kalshi_m = kalshi_keys[key]
                print(f"\n   Match: {key}")
                print(f"   - Polymarket: {poly_m.get('question', 'N/A')}")
                print(f"   - Kalshi: {kalshi_m.get('question', 'N/A')}")
        else:
            print(f"   ℹ No exact matches found yet")
            print(f"   - Polymarket normalized keys: {list(poly_keys.keys())[:3]}")
            print(f"   - Kalshi normalized keys: {list(kalshi_keys.keys())[:3]}")
    except Exception as e:
        print(f"   ✗ Error checking matches: {e}")
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == '__main__':
    test_crypto_apis()
