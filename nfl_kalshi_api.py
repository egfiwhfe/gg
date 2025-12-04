#!/usr/bin/env python3
"""
Kalshi API for NFL games
Fetches NFL game data from Kalshi
"""

from kalshi_api import KalshiAPI
import math
from nfl_team_mapping import normalize_team_name, get_team_info

class NFLKalshiAPI(KalshiAPI):
    def __init__(self):
        super().__init__()
        self.NFL_SERIES = "KXNFLGAME"

    def get_nfl_games(self):
        """
        Fetch NFL games from Kalshi
        Returns list of game dictionaries with standardized format
        """
        # Fetch markets filtered by NFL series
        markets = self.get_markets_by_ticker(self.NFL_SERIES, limit=500)

        # Filter for NFL markets
        nfl_markets = []
        for market in markets:
            ticker = market.get('ticker', '')
            if self.NFL_SERIES in ticker:
                nfl_markets.append(market)
        
        try:
            # Group markets by event (2 markets per game, one for each team)
            games_dict = {}
            for market in nfl_markets:
                event_ticker = market.get('event_ticker', '')
                ticker = market.get('ticker', '')
                team_name = market.get('yes_sub_title', '')

                if not event_ticker or not team_name:
                    continue

                # Normalize team name
                team_code = normalize_team_name(team_name, 'kalshi')
                if not team_code:
                    continue

                # Get probability directly from last_price (already in percentage)
                prob = market.get('last_price', 0)

                if event_ticker not in games_dict:
                    games_dict[event_ticker] = {'ticker': ticker}

                games_dict[event_ticker][team_code] = {
                    'name': team_name,
                    'prob': prob,
                    'team_code': team_code
                }

            # Convert to game format
            games = []
            for event_ticker, teams in games_dict.items():
                # Extract ticker first
                ticker = teams.get('ticker', '')
                # Get team codes (exclude 'ticker' key)
                team_codes = [k for k in teams.keys() if k != 'ticker']
                
                if len(team_codes) != 2:
                    continue

                team_codes = list(team_codes)
                team1_code = team_codes[0]
                team2_code = team_codes[1]

                team1_info = get_team_info(team1_code)
                team2_info = get_team_info(team2_code)

                if not team1_info or not team2_info:
                    continue

                # Determine home/away based on event title pattern
                # Kalshi format is usually "Away at Home"
                team1_data = teams[team1_code]
                team2_data = teams[team2_code]

                # Normalize probabilities to sum to exactly 100%
                away_raw = team1_data['prob']
                home_raw = team2_data['prob']
                total = away_raw + home_raw
                
                if total > 0:
                    # Convert to percentages
                    away_pct = (away_raw / total) * 100
                    home_pct = (home_raw / total) * 100
                    
                    # Floor both values
                    away_floor = math.floor(away_pct)
                    home_floor = math.floor(home_pct)
                    remainder = 100 - (away_floor + home_floor)
                    
                    # Give remainder to the smaller raw value
                    if away_raw <= home_raw:
                        away_prob = away_floor + remainder
                        home_prob = home_floor
                    else:
                        away_prob = away_floor
                        home_prob = home_floor + remainder
                else:
                    away_prob = 0
                    home_prob = 0

                # Create game entry (assume first team is away, second is home)
                game = {
                    'away_team': team1_info[0],  # Polymarket name for consistency
                    'home_team': team2_info[0],
                    'away_code': team1_code,
                    'home_code': team2_code,
                    'away_prob': away_prob,
                    'home_prob': home_prob,
                    'away_raw_price': away_raw,
                    'home_raw_price': home_raw,
                    'event_ticker': event_ticker,
                    'url': f'https://kalshi.com/markets/{ticker}' if ticker else '',
                }

                games.append(game)

            return games

        except Exception as e:
            print(f"Error fetching NFL games from Kalshi: {e}")
            return []



if __name__ == '__main__':
    # Test the API
    api = NFLKalshiAPI()
    games = api.get_nfl_games()
    print(f"\nFound {len(games)} NFL games:")
    for game in games[:5]:
        print(f"  {game['away_team']} @ {game['home_team']}: {game['away_prob']:.1f}% vs {game['home_prob']:.1f}%")
