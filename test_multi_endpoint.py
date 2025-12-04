#!/usr/bin/env python3
"""
Test script to verify the /api/odds/multi endpoint
"""

import requests
import json

def test_multi_endpoint():
    """Test the /api/odds/multi endpoint"""
    print("Testing /api/odds/multi endpoint...")
    print("=" * 80)
    
    try:
        response = requests.get('http://localhost:5001/api/odds/multi', timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error: HTTP {response.status_code}")
            print(response.text)
            return False
        
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ API returned success=False")
            print(f"Error: {data.get('error')}")
            return False
        
        print(f"✅ API call successful")
        print(f"\nStats:")
        stats = data.get('stats', {})
        print(f"  - Total games: {stats.get('total_games', 0)}")
        print(f"  - Polymarket total: {stats.get('poly_total', 0)}")
        print(f"  - Kalshi total: {stats.get('kalshi_total', 0)}")
        print(f"  - Matched games: {stats.get('matched', 0)}")
        print(f"  - Tradable markets: {stats.get('tradable_markets', 0)}")
        
        print(f"\nGames returned:")
        games = data.get('games', [])
        homepage_arb_games = data.get('homepage_arb_games', [])
        print(f"  - All games: {len(games)}")
        print(f"  - Arbitrage games: {len(homepage_arb_games)}")
        
        # Verify sports breakdown
        sport_counts = {}
        for game in games:
            sport = game.get('sport', 'unknown')
            sport_counts[sport] = sport_counts.get(sport, 0) + 1
        
        print(f"\nGames by sport:")
        for sport, count in sport_counts.items():
            print(f"  - {sport}: {count}")
        
        # Verify arbitrage games breakdown
        arb_sport_counts = {}
        for game in homepage_arb_games:
            sport = game.get('sport', 'unknown')
            arb_sport_counts[sport] = arb_sport_counts.get(sport, 0) + 1
        
        print(f"\nArbitrage games by sport:")
        for sport, count in arb_sport_counts.items():
            print(f"  - {sport}: {count}")
        
        # Show sample arbitrage game
        if homepage_arb_games:
            print(f"\n📊 Sample arbitrage game:")
            sample = homepage_arb_games[0]
            print(f"  - Game: {sample.get('away_team')} @ {sample.get('home_team')}")
            print(f"  - Sport: {sample.get('sport')}")
            print(f"  - Arbitrage Score: {sample.get('arbitrage_score', 0)}")
            arb = sample.get('riskFreeArb') or sample.get('risk_free_arb')
            if arb:
                print(f"  - ROI: {arb.get('roiPercent', 0):.2f}%")
                print(f"  - Edge: {arb.get('edge', 0):.2f}¢")
                print(f"  - Best Away From: {arb.get('bestAwayFrom')}")
                print(f"  - Best Home From: {arb.get('bestHomeFrom')}")
        
        # Verify ONLY NBA, NFL, NHL are present
        allowed_sports = {'NBA', 'NFL', 'NHL'}
        invalid_sports = set(sport_counts.keys()) - allowed_sports
        if invalid_sports:
            print(f"\n⚠️  WARNING: Found non-NBA/NFL/NHL sports: {invalid_sports}")
            return False
        
        print(f"\n✅ All checks passed!")
        return True
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_multi_endpoint()
    exit(0 if success else 1)
