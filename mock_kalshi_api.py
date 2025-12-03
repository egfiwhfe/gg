#!/usr/bin/env python3
"""
Mock Kalshi API for testing purposes when real API is unavailable
"""

import random
import json
from typing import List, Dict
from kalshi_api import KalshiAPI
from team_mapping import normalize_team_name

class MockKalshiAPI(KalshiAPI):
    """
    Mock Kalshi API that generates realistic test data
    """
    
    def get_markets_by_ticker(self, series_ticker: str, limit: int = 500) -> List[Dict]:
        """
        Generate mock markets for testing
        """
        print(f"Generating mock Kalshi markets for series {series_ticker}...")
        
        # Mock team data based on sport
        sport_teams = self._get_mock_teams(series_ticker)
        if not sport_teams:
            return []
        
        mock_markets = []
        
        # Generate mock matchups
        for i in range(min(20, limit // 2)):  # Generate reasonable number of games
            if i >= len(sport_teams) - 1:
                break
                
            away_team = sport_teams[i]
            home_team = sport_teams[i + 1] if i + 1 < len(sport_teams) else sport_teams[0]
            
            # Generate realistic odds with some arbitrage opportunities
            away_price = round(random.uniform(25, 75), 1)
            home_price = round(100 - away_price + random.uniform(-5, 5), 1)
            
            # Ensure prices sum to around 100
            if away_price + home_price > 110:
                home_price = 110 - away_price
            elif away_price + home_price < 90:
                home_price = 90 - away_price
            
            mock_market = {
                'id': f"mock-{series_ticker}-{i}",
                'ticker': f"{series_ticker}-2024{i:02d}-{away_team[:3].upper()}",
                'title': f"{away_team} vs {home_team} Winner?",
                'subtitle': away_team,
                'outcome_prices': json.dumps([away_price, home_price]),
                'status': 'open',
                'expiry_date': '2024-12-31T23:59:59Z'
            }
            
            mock_markets.append(mock_market)
        
        print(f"Generated {len(mock_markets)} mock markets for {series_ticker}")
        return mock_markets
    
    def _get_mock_teams(self, series_ticker: str) -> List[str]:
        """Get mock team names based on series ticker"""
        if 'NBA' in series_ticker:
            return [
                'Lakers', 'Warriors', 'Celtics', 'Heat', 'Nets', 'Bucks', 
                'Nuggets', 'Suns', 'Clippers', 'Mavericks', '76ers', 'Raptors'
            ]
        elif 'NFL' in series_ticker:
            return [
                'Chiefs', 'Bills', 'Bengals', 'Ravens', 'Dolphins', 'Patriots',
                'Jets', 'Browns', 'Steelers', 'Ravens', 'Bengals', 'Browns'
            ]
        elif 'NHL' in series_ticker:
            return [
                'Golden Knights', 'Lightning', 'Avalanche', 'Hurricanes', 'Rangers',
                'Bruins', 'Maple Leafs', 'Oilers', 'Canucks', 'Kraken'
            ]
        elif any(keyword in series_ticker for keyword in ['SOCCER', 'EPL', 'UCL', 'UEL']):
            return [
                'Manchester United', 'Manchester City', 'Liverpool', 'Arsenal', 'Chelsea',
                'Barcelona', 'Real Madrid', 'Bayern Munich', 'PSG', 'Juventus',
                'Inter Milan', 'AC Milan', 'Ajax', 'Porto', 'Benfica', 'Atletico Madrid'
            ]
        elif any(keyword in series_ticker for keyword in ['CS2', 'CSGO']):
            return [
                'NAVI', 'FaZe', 'G2', 'Vitality', 'Astralis', 'Heroic',
                'Liquid', 'Cloud9', 'FURIA', 'Complexity'
            ]
        elif 'LOL' in series_ticker:
            return [
                'T1', 'Gen.G', 'DWG KIA', 'JD Gaming', 'Bilibili Gaming',
                'Fnatic', 'G2 Esports', 'Team Liquid', 'Cloud9', '100 Thieves'
            ]
        elif 'DOTA' in series_ticker:
            return [
                'Team Spirit', 'OG', 'Secret', 'Alliance', 'Nigma',
                'Evil Geniuses', 'Team Liquid', 'Virtus.pro', 'NaVi'
            ]
        else:
            return [
                'Team Alpha', 'Team Beta', 'Team Gamma', 'Team Delta',
                'Team Epsilon', 'Team Zeta', 'Team Eta', 'Team Theta'
            ]

# Factory function to get the appropriate API
def get_kalshi_api():
    """Get Kalshi API (mock if real API is unavailable)"""
    try:
        # Try real API first
        api = KalshiAPI()
        # Test if it works
        test_markets = api.get_markets_by_ticker('KXNBAGAME', limit=1)
        if len(test_markets) == 0:
            # If no markets returned, likely auth issue, use mock
            print("⚠️  Kalshi API authentication failed, using mock data for testing")
            return MockKalshiAPI()
        return api
    except Exception as e:
        print(f"⚠️  Kalshi API error: {e}, using mock data for testing")
        return MockKalshiAPI()