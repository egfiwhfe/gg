#!/usr/bin/env python3
"""
The Odds API Aggregator
Fetches odds from multiple sportsbooks (DraftKings, FanDuel, BetMGM, etc.)
Get your free API key at: https://the-odds-api.com/
"""

import requests
from typing import List, Dict, Optional
from team_mapping import normalize_team_name
from config import API_KEYS

class OddsAPIAggregator:
    BASE_URL = "https://api.the-odds-api.com/v4"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or API_KEYS.get('ODDS_API_KEY', '')
        self.session = requests.Session()

    def get_nba_games(self) -> List[Dict]:
        """
        Fetch NBA games from The Odds API
        Returns aggregated odds from multiple sportsbooks
        """
        if not self.api_key:
            print("⚠️  Odds API key not configured. Add key to config.py")
            return []

        url = f"{self.BASE_URL}/sports/basketball_nba/odds/"
        params = {
            'apiKey': self.api_key,
            'regions': 'us',  # US sportsbooks
            'markets': 'h2h',  # Head to head (moneyline)
            'oddsFormat': 'decimal'
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            events = response.json()

            # Check remaining requests
            remaining = response.headers.get('x-requests-remaining', 'unknown')
            print(f"📊 Odds API requests remaining: {remaining}")

            games = []
            for event in events:
                game = self._parse_event(event)
                if game:
                    games.append(game)

            return games

        except requests.RequestException as e:
            print(f"Error fetching Odds API data: {e}")
            return []

    def _parse_event(self, event: Dict) -> Optional[Dict]:
        """Parse a single event from The Odds API"""
        try:
            home_team_raw = event.get('home_team', '')
            away_team_raw = event.get('away_team', '')

            # Normalize team names
            home_code = normalize_team_name(home_team_raw, 'odds_api')
            away_code = normalize_team_name(away_team_raw, 'odds_api')

            if not home_code or not away_code:
                print(f"Warning: Could not normalize teams: {away_team_raw} @ {home_team_raw}")
                return None

            # Get bookmakers data
            bookmakers = event.get('bookmakers', [])
            if not bookmakers:
                return None

            # Aggregate odds from multiple bookmakers (use average or best)
            all_home_odds = []
            all_away_odds = []

            for bookmaker in bookmakers:
                markets = bookmaker.get('markets', [])
                for market in markets:
                    if market.get('key') == 'h2h':
                        outcomes = market.get('outcomes', [])
                        for outcome in outcomes:
                            team_name = outcome.get('name', '')
                            price = outcome.get('price', 0)  # Decimal odds

                            # Convert decimal odds to probability
                            prob = (1 / price) * 100 if price > 0 else 0

                            if team_name == home_team_raw:
                                all_home_odds.append(prob)
                            elif team_name == away_team_raw:
                                all_away_odds.append(prob)

            if not all_home_odds or not all_away_odds:
                return None

            # Use average probability
            import statistics
            home_prob = statistics.mean(all_home_odds)
            away_prob = statistics.mean(all_away_odds)

            # Normalize to 100%
            total = home_prob + away_prob
            if total > 0:
                home_prob = (home_prob / total) * 100
                away_prob = (away_prob / total) * 100

            return {
                'away_team': away_team_raw,
                'home_team': home_team_raw,
                'away_code': away_code,
                'home_code': home_code,
                'away_prob': round(away_prob, 1),
                'home_prob': round(home_prob, 1),
                'commence_time': event.get('commence_time', ''),
                'num_bookmakers': len(bookmakers),
                'bookmakers': [b.get('key') for b in bookmakers[:5]],  # Top 5 bookmakers
                'url': f"https://the-odds-api.com"  # Generic URL
            }

        except Exception as e:
            print(f"Error parsing event: {e}")
            return None


if __name__ == '__main__':
    # Test the API
    api = OddsAPIAggregator()
    games = api.get_nba_games()

    if games:
        print(f"\n✅ Found {len(games)} NBA games from Odds API:")
        for game in games[:3]:
            print(f"  {game['away_team']} @ {game['home_team']}")
            print(f"    Odds: {game['away_prob']}% vs {game['home_prob']}%")
            print(f"    Bookmakers: {', '.join(game['bookmakers'])}")
    else:
        print("\n⚠️  No games found. Make sure to add your API key to config.py")
