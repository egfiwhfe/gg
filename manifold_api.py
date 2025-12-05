#!/usr/bin/env python3
"""
Manifold Markets API
Community-driven prediction market
Free API, no key required
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from team_mapping import normalize_team_name

class ManifoldAPI:
    BASE_URL = "https://api.manifold.markets/v0"

    def __init__(self):
        self.session = requests.Session()

    def get_nba_games(self) -> List[Dict]:
        """
        Fetch NBA games from Manifold Markets
        Note: Manifold focuses more on long-term markets,
        may not have every daily game
        """
        url = f"{self.BASE_URL}/search-markets"

        # Search for today's NBA games
        today = datetime.now().strftime('%Y-%m-%d')
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

        games = []

        # Try searching for specific matchups
        search_terms = [
            f"NBA {today}",
            f"NBA {tomorrow}",
            "NBA tonight",
            "NBA today"
        ]

        for term in search_terms:
            params = {
                'term': term,
                'limit': 20,
                'filter': 'open'  # Only open markets
            }

            try:
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                markets = response.json()

                for market in markets:
                    game = self._parse_market(market)
                    if game and game not in games:
                        games.append(game)

            except requests.RequestException as e:
                print(f"Error fetching Manifold data for '{term}': {e}")
                continue

        return games

    def _parse_market(self, market: Dict) -> Optional[Dict]:
        """Parse a Manifold market into our game format"""
        try:
            question = market.get('question', '')

            # Only process binary markets with team vs team format
            if market.get('outcomeType') != 'BINARY':
                return None

            if ' vs ' not in question and ' @ ' not in question:
                return None

            # Parse team names
            if ' vs ' in question:
                parts = question.split(' vs ')
            else:
                parts = question.split(' @ ')

            if len(parts) != 2:
                return None

            away_team = parts[0].strip()
            home_team = parts[1].strip().rstrip('?')

            # Normalize team names
            away_code = normalize_team_name(away_team, 'manifold')
            home_code = normalize_team_name(home_team, 'manifold')

            if not away_code or not home_code:
                return None

            # Get probability
            probability = market.get('probability', 0) * 100  # Convert to percentage

            # Manifold probabilities are for "YES" outcome
            # We need to determine which team that refers to
            # Usually it's the away team (first mentioned)
            away_prob = round(probability, 1)
            home_prob = round(100 - probability, 1)

            return {
                'away_team': away_team,
                'home_team': home_team,
                'away_code': away_code,
                'home_code': home_code,
                'away_prob': away_prob,
                'home_prob': home_prob,
                'close_time': market.get('closeTime', ''),
                'url': market.get('url', ''),
                'volume': market.get('volume', 0),
                'liquidity': market.get('totalLiquidity', 0)
            }

        except Exception as e:
            print(f"Error parsing Manifold market: {e}")
            return None


if __name__ == '__main__':
    # Test the API
    api = ManifoldAPI()
    games = api.get_nba_games()

    print(f"\n🔮 Found {len(games)} NBA games from Manifold Markets:")
    for game in games[:5]:
        print(f"  {game['away_team']} @ {game['home_team']}")
        print(f"    Odds: {game['away_prob']}% vs {game['home_prob']}%")
        print(f"    Volume: ${game['volume']:.0f}, Liquidity: ${game['liquidity']:.0f}")
