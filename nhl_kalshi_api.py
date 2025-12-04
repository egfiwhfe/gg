#!/usr/bin/env python3
"""Kalshi API for NHL games"""

from kalshi_api import KalshiAPI
import math
from typing import List, Dict
from collections import defaultdict
from nhl_team_mapping import normalize_team_name


class NHLKalshiAPI(KalshiAPI):
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    NHL_SERIES = "KXNHLGAME"

    def __init__(self):
        super().__init__()

    def get_nhl_games(self) -> List[Dict]:
        """Get NHL games from Kalshi"""
        # Fetch markets filtered by NHL series
        markets = self.get_markets_by_ticker(self.NHL_SERIES, limit=500)

        # Filter for NHL markets
        nhl_markets = []
        for market in markets:
            ticker = market.get('ticker', '')
            if self.NHL_SERIES in ticker:
                nhl_markets.append(market)

        try:
            games_dict = defaultdict(dict)

            for market in nhl_markets:
                title = market.get('title', '')
                if 'Winner?' not in title:
                    continue

                ticker = market.get('ticker', '')
                parts = ticker.split('-')
                if len(parts) < 3:
                    continue

                game_id = parts[1]
                team_code = parts[2]

                title_clean = title.replace(' Winner?', '')
                if ' vs ' in title_clean:
                    teams = title_clean.split(' vs ')
                elif ' at ' in title_clean:
                    teams = title_clean.split(' at ')
                else:
                    continue

                if len(teams) != 2:
                    continue

                away_team = teams[0].strip()
                home_team = teams[1].strip()

                away_code = normalize_team_name(away_team, 'kalshi')
                home_code = normalize_team_name(home_team, 'kalshi')

                if not away_code or not home_code:
                    continue

                last_price = market.get('last_price', 0)
                yes_bid = market.get('yes_bid', 0)
                yes_ask = market.get('yes_ask', 0)
                
                # Use last_price if available, otherwise use mid-point of bid/ask
                # Prioritize bid/ask if both available to avoid stale prices
                if yes_bid > 0 and yes_ask > 0:
                    probability = (yes_bid + yes_ask) / 2
                elif last_price > 0:
                    probability = last_price
                elif yes_ask > 0:
                    probability = yes_ask
                elif yes_bid > 0:
                    probability = yes_bid
                else:
                    probability = 0

                if game_id not in games_dict:
                    games_dict[game_id] = {
                        'platform': 'Kalshi',
                        'away_team': away_team,
                        'home_team': home_team,
                        'away_code': away_code,
                        'home_code': home_code,
                        'close_time': market.get('close_time', ''),
                        'ticker': ticker,
                    }

                if team_code == away_code or normalize_team_name(team_code, 'kalshi') == away_code:
                    games_dict[game_id]['away_raw'] = probability
                elif team_code == home_code or normalize_team_name(team_code, 'kalshi') == home_code:
                    games_dict[game_id]['home_raw'] = probability

            games = []
            for game_id, game_data in games_dict.items():
                if 'away_raw' in game_data and 'home_raw' in game_data:
                    away_raw = game_data['away_raw']
                    home_raw = game_data['home_raw']
                    total = away_raw + home_raw

                    if total > 0:
                        away_pct = (away_raw / total) * 100
                        home_pct = (home_raw / total) * 100

                        away_floor = math.floor(away_pct)
                        home_floor = math.floor(home_pct)
                        remainder = 100 - (away_floor + home_floor)

                        if away_raw <= home_raw:
                            away_prob = away_floor + remainder
                            home_prob = home_floor
                        else:
                            away_prob = away_floor
                            home_prob = home_floor + remainder
                    else:
                        away_prob = 0
                        home_prob = 0

                    game_data['away_prob'] = away_prob
                    game_data['home_prob'] = home_prob
                    game_data['away_raw_price'] = away_raw
                    game_data['home_raw_price'] = home_raw

                    ticker = game_data.get('ticker', '')
                    if ticker:
                        game_data['url'] = f'https://kalshi.com/markets/{ticker}'

                    games.append(game_data)

            return games

        except Exception as e:
            print(f"Error fetching NHL data from Kalshi: {e}")
            return []



if __name__ == '__main__':
    api = NHLKalshiAPI()
    games = api.get_nhl_games()
    print(f"\nFound {len(games)} NHL games on Kalshi:")
    for game in games[:5]:
        print(f"  {game['away_team']} @ {game['home_team']}: {game['away_prob']}% vs {game['home_prob']}%")
