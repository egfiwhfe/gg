#!/usr/bin/env python3
"""Polymarket API for NHL games"""

from polymarket_api import PolymarketAPI
import json
import math
from nhl_team_mapping import normalize_team_name


class NHLPolymarketAPI(PolymarketAPI):
    def __init__(self):
        super().__init__()
        self.NHL_TAG_ID = "899"

    def get_nhl_games(self):
        """Fetch NHL games from Polymarket"""
        # Fetch events filtered by NHL tag
        events = self.get_events_by_tag(self.NHL_TAG_ID, limit=500)

        games = []
        for event in events:
            # Check for NHL tag
            has_nhl_tag = False
            for tag in event.get('tags', []):
                if str(tag.get('id', '')) == self.NHL_TAG_ID:
                    has_nhl_tag = True
                    break
            
            if not has_nhl_tag:
                continue

            game = self._parse_game(event)
            if game:
                games.append(game)

        return games

    def _parse_game(self, event):
        """Parse a single game event"""
        try:
            title = event.get('title', '')

            if ' vs. ' not in title and ' vs ' not in title:
                return None

            if ' vs. ' in title:
                teams = title.split(' vs. ')
            else:
                teams = title.split(' vs ')

            if len(teams) != 2:
                return None

            away_team = teams[0].strip()
            home_team = teams[1].strip()

            away_code = normalize_team_name(away_team, 'polymarket')
            home_code = normalize_team_name(home_team, 'polymarket')

            if not away_code or not home_code:
                return None

            winner_market = None
            for market in event.get('markets', []):
                question = market.get('question', '')
                if question == title:
                    winner_market = market
                    break

            if not winner_market:
                for market in event.get('markets', []):
                    question = market.get('question', '')
                    if 'Moneyline' in question and '1H' not in question and '1P' not in question:
                        winner_market = market
                        break

            if not winner_market:
                return None

            outcomes = json.loads(winner_market.get('outcomes', '[]'))
            prices = json.loads(winner_market.get('outcomePrices', '[]'))

            if len(outcomes) != 2 or len(prices) != 2:
                return None

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

            prob1 = outcome_data[0]['raw_prob']
            prob2 = outcome_data[1]['raw_prob']

            floor1 = math.floor(prob1)
            floor2 = math.floor(prob2)
            remainder = 100 - (floor1 + floor2)

            if prob1 <= prob2:
                outcome_data[0]['prob'] = floor1 + remainder
                outcome_data[1]['prob'] = floor2
            else:
                outcome_data[0]['prob'] = floor1
                outcome_data[1]['prob'] = floor2 + remainder

            probs = {
                outcome_data[0]['code']: outcome_data[0]['prob'],
                outcome_data[1]['code']: outcome_data[1]['prob']
            }

            raw_probs = {
                outcome_data[0]['code']: outcome_data[0]['raw_prob'],
                outcome_data[1]['code']: outcome_data[1]['raw_prob']
            }

            slug = event.get('slug', '')
            game = {
                'away_team': away_team,
                'home_team': home_team,
                'away_code': away_code,
                'home_code': home_code,
                'away_prob': probs.get(away_code, 0),
                'home_prob': probs.get(home_code, 0),
                'away_raw_price': raw_probs.get(away_code, 0),
                'home_raw_price': raw_probs.get(home_code, 0),
                'market_id': winner_market.get('id'),
                'end_date': event.get('endDate', ''),
                'slug': slug,
                'url': f'https://polymarket.com/event/{slug}' if slug else '',
            }

            return game

        except Exception as e:
            return None


if __name__ == '__main__':
    api = NHLPolymarketAPI()
    games = api.get_nhl_games()
    print(f"\nFound {len(games)} NHL games:")
    for game in games[:5]:
        print(f"  {game['away_team']} @ {game['home_team']}: {game['away_prob']}% vs {game['home_prob']}%")
