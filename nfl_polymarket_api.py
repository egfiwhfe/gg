#!/usr/bin/env python3
"""
Polymarket API for NFL games
Fetches NFL game data from Polymarket
"""

from polymarket_api import PolymarketAPI
from nfl_team_mapping import normalize_team_name, get_team_info
import json

class NFLPolymarketAPI(PolymarketAPI):
    def __init__(self):
        super().__init__()
        self.NFL_TAG_ID = "450"

    def get_nfl_games(self):
        """
        Fetch NFL games from Polymarket
        Returns list of game dictionaries with standardized format
        """
        # Fetch events filtered by NFL tag
        events = self.get_events_by_tag(self.NFL_TAG_ID, limit=500)

        games = []
        for event in events:
            # Check if event has NFL tag
            has_nfl_tag = False
            for tag in event.get('tags', []):
                if str(tag.get('id', '')) == self.NFL_TAG_ID:
                    has_nfl_tag = True
                    break
            
            if not has_nfl_tag:
                continue
            
            game = self._parse_game(event)
            if game:
                games.append(game)

        return games

    def _parse_game(self, event):
        """Parse a single game event"""
        try:
            title = event.get('title', '')

            # Parse team names from title (format: "Team1 vs. Team2" or "Team1 vs Team2")
            if ' vs. ' in title:
                teams = title.split(' vs. ')
            elif ' vs ' in title:
                teams = title.split(' vs ')
            else:
                return None

            if len(teams) != 2:
                return None

            team1_name = teams[0].strip()
            team2_name = teams[1].strip()

            # Normalize team names to codes
            team1_code = normalize_team_name(team1_name, 'polymarket')
            team2_code = normalize_team_name(team2_name, 'polymarket')

            if not team1_code or not team2_code:
                print(f"Could not map teams: {team1_name} vs {team2_name}")
                return None

            # Find the moneyline market (exact title match)
            winner_market = None
            for market in event.get('markets', []):
                question = market.get('question', '')
                # The moneyline market has the exact same title as the event
                if question == title:
                    winner_market = market
                    break

            if not winner_market:
                print(f"No moneyline market found for: {title}")
                return None

            # Parse outcomes and prices (they are JSON strings)
            try:
                import math
                outcomes = json.loads(winner_market.get('outcomes', '[]'))
                prices = json.loads(winner_market.get('outcomePrices', '[]'))

                if len(outcomes) != 2 or len(prices) != 2:
                    return None

                # Process outcomes in their original order
                outcome_data = []
                for outcome, price in zip(outcomes, prices):
                    team_code = normalize_team_name(outcome, 'polymarket')
                    if team_code:
                        outcome_data.append({
                            'code': team_code,
                            'raw_prob': float(price) * 100
                        })

                if len(outcome_data) != 2:
                    return None

                # Normalize probabilities - give remainder to SMALLER value
                prob1 = outcome_data[0]['raw_prob']
                prob2 = outcome_data[1]['raw_prob']

                floor1 = math.floor(prob1)
                floor2 = math.floor(prob2)
                remainder = 100 - (floor1 + floor2)

                # Give remainder to the SMALLER raw probability
                if prob1 <= prob2:
                    outcome_data[0]['prob'] = floor1 + remainder
                    outcome_data[1]['prob'] = floor2
                else:
                    outcome_data[0]['prob'] = floor1
                    outcome_data[1]['prob'] = floor2 + remainder

                # Map to team codes
                probs = {
                    outcome_data[0]['code']: outcome_data[0]['prob'],
                    outcome_data[1]['code']: outcome_data[1]['prob']
                }

                raw_probs = {
                    outcome_data[0]['code']: outcome_data[0]['raw_prob'],
                    outcome_data[1]['code']: outcome_data[1]['raw_prob']
                }

                # Get team info
                team1_info = get_team_info(team1_code)
                team2_info = get_team_info(team2_code)

                # Build game data
                slug = event.get('slug', '')
                game = {
                    'away_team': team1_info[0],  # Polymarket name
                    'home_team': team2_info[0],
                    'away_code': team1_code,
                    'home_code': team2_code,
                    'away_prob': probs.get(team1_code, 0),
                    'home_prob': probs.get(team2_code, 0),
                    'away_raw_price': raw_probs.get(team1_code, 0),
                    'home_raw_price': raw_probs.get(team2_code, 0),
                    'market_id': winner_market.get('id'),
                    'end_date': event.get('endDate', ''),
                    'event_id': event.get('id', ''),
                    'slug': slug,
                    'url': f'https://polymarket.com/event/{slug}' if slug else '',
                }

                return game

            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing outcomes/prices for {title}: {e}")
                return None

        except Exception as e:
            print(f"Error parsing game: {e}")
            return None


if __name__ == '__main__':
    # Test the API
    api = NFLPolymarketAPI()
    games = api.get_nfl_games()
    print(f"\nFound {len(games)} NFL games:")
    for game in games[:5]:
        print(f"  {game['away_team']} @ {game['home_team']}: {game['away_prob']}% vs {game['home_prob']}%")
