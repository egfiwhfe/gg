#!/usr/bin/env python3
"""
Test script for general markets (Soccer, Esports, Politics, etc.)
"""

from general_markets_api import GeneralPolymarketAPI, GeneralKalshiAPI
import json

def test_general_markets():
    print("=" * 70)
    print("Testing General Markets APIs")
    print("=" * 70)
    
    categories_to_test = ['SOCCER', 'ESPORTS', 'POLITICS']
    
    for category in categories_to_test:
        print(f"\n{'='*70}")
        print(f"Testing {category} Markets")
        print(f"{'='*70}")
        
        # Test Polymarket
        print(f"\n1. Testing Polymarket {category} API...")
        try:
            poly_api = GeneralPolymarketAPI()
            poly_markets = poly_api.get_markets_by_category(category, limit=5)
            print(f"   ✓ Found {len(poly_markets)} Polymarket {category} markets")
            if poly_markets:
                sample = poly_markets[0]
                print(f"   Sample market:")
                print(f"   - Question: {sample.get('question', 'N/A')[:80]}...")
                print(f"   - Away: {sample.get('away_team', 'N/A')[:60]}...")
                print(f"   - Home: {sample.get('home_team', 'N/A')[:60]}...")
                print(f"   - Away Code: {sample.get('away_code', 'N/A')[:40]}...")
                print(f"   - Home Code: {sample.get('home_code', 'N/A')[:40]}...")
                print(f"   - Away Prob: {sample.get('away_prob', 0)}%")
                print(f"   - Home Prob: {sample.get('home_prob', 0)}%")
                print(f"   - URL: {sample.get('url', 'N/A')}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Test Kalshi
        print(f"\n2. Testing Kalshi {category} API...")
        try:
            kalshi_api = GeneralKalshiAPI()
            kalshi_markets = kalshi_api.get_markets_by_category(category, limit=5)
            print(f"   ✓ Found {len(kalshi_markets)} Kalshi {category} markets")
            if kalshi_markets:
                sample = kalshi_markets[0]
                print(f"   Sample market:")
                print(f"   - Question: {sample.get('question', 'N/A')[:80]}...")
                print(f"   - Away: {sample.get('away_team', 'N/A')[:60]}...")
                print(f"   - Home: {sample.get('home_team', 'N/A')[:60]}...")
                print(f"   - Away Code: {sample.get('away_code', 'N/A')[:40]}...")
                print(f"   - Home Code: {sample.get('home_code', 'N/A')[:40]}...")
                print(f"   - Away Prob: {sample.get('away_prob', 0)}%")
                print(f"   - Home Prob: {sample.get('home_prob', 0)}%")
                print(f"   - URL: {sample.get('url', 'N/A')}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)

if __name__ == '__main__':
    test_general_markets()
