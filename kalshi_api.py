import requests
import math
import json
from typing import List, Dict
from collections import defaultdict
from team_mapping import normalize_team_name

class KalshiAPI:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    NBA_SERIES = "KXNBAGAME"
    # Expanded series tickers for broader coverage
    ALL_SPORTS_TICKERS = [
        "KXNBAGAME", "KXNBA",  # Basketball
        "KXNFLGAME", "KXNFL", "KXNFLSPREAD", "KXNFLML", # Football
        "KXNHLGAME", "KXNHL", "KXUHFH",  # Hockey
        "KXSOCCER", "KXEPLGAME", "KXUCLGAME", "KXUELGAME", "KXSOCCERGAME", "KXLALIGA", "KXFAWC", # Football/Soccer
        "KXWNBA", "KXWNFL", "KXCOLLEGEFB", "KXCOLLEGEBB", "KXCOLLEGEHOOPS", # College sports
        "KXCRICKET", "KXRUGBY", "KXTENNIS", "KXGOLF", "KXBOXING", "KXUFC", # Other sports
        "KXESPORTS", "KXCS2", "KXDOTA", "KXVALORANT"  # Esports
     ]

    def __init__(self):
        self.session = requests.Session()

    def get_market(self, ticker: str) -> Dict:
        """
        Get a single market by ticker
        """
        if not ticker:
            return None
            
        url = f"{self.BASE_URL}/markets/{ticker}"
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return data.get('market')
        except requests.RequestException as e:
            print(f"Error fetching market {ticker}: {e}")
            return None

    def get_markets_by_ticker(self, series_ticker: str, limit: int = 500) -> List[Dict]:
        """
        Get markets from Kalshi filtered by series ticker
        """
        all_markets = []
        cursor = None
        batch_size = 100

        print(f"Fetching Kalshi markets for series {series_ticker}...")

        while len(all_markets) < limit:
            url = f"{self.BASE_URL}/markets"
            params = {
                'status': 'open',
                'series_ticker': series_ticker,
                'limit': batch_size
            }
            if cursor:
                params['cursor'] = cursor

            try:
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                markets = data.get('markets', [])

                if not markets:
                    break

                all_markets.extend(markets)
                cursor = data.get('cursor')

                print(f"Fetched {len(all_markets)} markets for series {series_ticker}...")

                if not cursor or len(markets) < batch_size:
                    break

            except requests.RequestException as e:
                print(f"Error fetching batch: {e}")
                break

        return all_markets

    def get_all_markets(self, limit: int = 500) -> List[Dict]:
        """
        Get all active markets from Kalshi
        
        Args:
            limit: Maximum number of markets to fetch
            
        Returns:
            List of all market dictionaries
        """
        all_markets = []
        cursor = None
        batch_size = 100
        
        print("Fetching all Kalshi markets...")
        
        while len(all_markets) < limit:
            url = f"{self.BASE_URL}/markets"
            params = {
                'status': 'open',
                'limit': batch_size
            }
            if cursor:
                params['cursor'] = cursor
            
            try:
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                markets = data.get('markets', [])
                
                if not markets:
                    break
                    
                all_markets.extend(markets)
                cursor = data.get('cursor')
                
                print(f"Fetched {len(all_markets)} markets so far...")
                
                if not cursor or len(markets) < batch_size:
                    break
                    
            except requests.RequestException as e:
                print(f"Error fetching batch: {e}")
                break
                
        return all_markets

    def get_nba_games(self) -> List[Dict]:
        """
        Get NBA games from Kalshi

        Returns:
            List of game dictionaries with standardized format
        """
        # Fetch markets filtered by NBA series
        markets = self.get_markets_by_ticker(self.NBA_SERIES, limit=500)

        # Group markets by game (each game has 2 markets, one for each team)
        games_dict = defaultdict(dict)

        for market in markets:
            # Check if market belongs to NBA series (double check)
            ticker = market.get('ticker', '')
            if self.NBA_SERIES not in ticker:
                continue


            title = market.get('title', '')

            # Filter for Winner markets only
            if 'Winner?' not in title:
                continue

            # Extract game identifier from ticker
            # Ticker format: KXNBAGAME-25NOV16BKNWAS-BKN
            parts = ticker.split('-')
            if len(parts) < 3:
                continue

            game_id = parts[1]  # e.g., "25NOV16BKNWAS"
            team_code = parts[2]  # e.g., "BKN" or "WAS"

            # Extract team names from title
            # Format: "Brooklyn vs Washington Winner?"
            title_clean = title.replace(' Winner?', '')
            teams = title_clean.split(' vs ')
            if len(teams) != 2:
                continue

            away_team = teams[0].strip()
            home_team = teams[1].strip()

            # Get team codes
            away_code = normalize_team_name(away_team, 'kalshi')
            home_code = normalize_team_name(home_team, 'kalshi')

            if not away_code or not home_code:
                # print(f"Warning: Could not normalize Kalshi teams: {away_team} vs {home_team}")
                continue

            # Get probability directly from last_price (already in percentage)
            last_price = market.get('last_price', 0)
            probability = last_price  # last_price is already the correct percentage

            # Store in games_dict
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

            # Add probability for this team
            if team_code == away_code:
                games_dict[game_id]['away_prob'] = probability
                games_dict[game_id]['away_ticker'] = ticker
            elif team_code == home_code:
                games_dict[game_id]['home_prob'] = probability
                games_dict[game_id]['home_ticker'] = ticker

        # Convert to list and filter complete games (with both probabilities)
        games = []
        for game_id, game_data in games_dict.items():
            if 'away_prob' in game_data and 'home_prob' in game_data:
                # Normalize probabilities to sum to exactly 100%
                away_raw = game_data['away_prob']
                home_raw = game_data['home_prob']
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

                # Update game data with normalized values
                game_data['away_prob'] = away_prob
                game_data['home_prob'] = home_prob
                game_data['away_raw_price'] = away_raw
                game_data['home_raw_price'] = home_raw

                # Add Kalshi market URL
                ticker = game_data.get('ticker', '')
                if ticker:
                    game_data['url'] = f'https://kalshi.com/markets/{ticker}'

                games.append(game_data)

        return games

    def get_today_games(self) -> List[Dict]:
        """Get today's NBA games (Kalshi API doesn't have easy date filtering, returns all open)"""
        return self.get_nba_games()

    def get_all_sports_games(self) -> List[Dict]:
        """
        Get games from all sports categories for broader market coverage
        """
        all_games = []
        seen_tickers = set()  # Avoid duplicates using ticker instead of id

        for series_ticker in self.ALL_SPORTS_TICKERS:
            try:
                markets = self.get_markets_by_ticker(series_ticker, limit=500)
                
                # Group markets by game (each game has 2 markets, one for each team)
                games_dict = defaultdict(dict)
                
                for market in markets:
                    ticker = market.get('ticker')
                    if not ticker or ticker in seen_tickers:
                        continue
                    seen_tickers.add(ticker)

                    # Process each market and group by game
                    game_data = self._process_market_for_all_sports_v2(market, series_ticker)
                    if game_data:
                        game_id = game_data.get('game_id')
                        if game_id:
                            # Merge data for this game
                            if game_id not in games_dict:
                                games_dict[game_id] = {
                                    'platform': 'Kalshi',
                                    'away_team': game_data['away_team'],
                                    'home_team': game_data['home_team'],
                                    'away_code': game_data['away_code'],
                                    'home_code': game_data['home_code'],
                                    'close_time': market.get('close_time', ''),
                                    'sport': game_data['sport'],
                                }
                            
                            # Add probability for this team
                            if game_data['team_code'] == game_data['away_code']:
                                games_dict[game_id]['away_prob'] = game_data['probability']
                                games_dict[game_id]['away_raw_price'] = game_data['raw_price']
                                games_dict[game_id]['away_ticker'] = market.get('ticker')
                            elif game_data['team_code'] == game_data['home_code']:
                                games_dict[game_id]['home_prob'] = game_data['probability']
                                games_dict[game_id]['home_raw_price'] = game_data['raw_price']
                                games_dict[game_id]['home_ticker'] = market.get('ticker')

                # Convert to list and filter complete games
                for game_id, game_data in games_dict.items():
                    if ('away_prob' in game_data and 'home_prob' in game_data and
                        'away_raw_price' in game_data and 'home_raw_price' in game_data):
                        
                        # Normalize probabilities to sum to exactly 100%
                        away_raw = game_data['away_raw_price']
                        home_raw = game_data['home_raw_price']
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

                        # Update game data with normalized values
                        game_data['away_prob'] = away_prob
                        game_data['home_prob'] = home_prob
                        game_data['away_raw_price'] = away_raw
                        game_data['home_raw_price'] = home_raw
                        
                        # Add URL and other fields
                        game_data['url'] = f'https://kalshi.com/markets/{game_data.get("away_ticker", "")}'
                        game_data['market_id'] = game_data.get('away_ticker', '')
                        game_data['end_date'] = game_data.get('close_time', '')
                        
                        all_games.append(game_data)

            except Exception as e:
                print(f"Error processing series {series_ticker}: {e}")
                continue

        return all_games

    def _process_market_for_all_sports_v2(self, market: Dict, series_ticker: str) -> Dict:
        """
        Process a single market for any sport category using real API data structure
        """
        title = market.get('title', '')
        ticker = market.get('ticker', '')

        # Skip non-vs markets
        if ' vs ' not in title:
            return None

        # Clean title - remove common suffixes
        clean_title = title.replace(' Winner?', '').replace(' winner?', '').strip()

        # Extract team names
        teams = clean_title.split(' vs ')
        if len(teams) != 2:
            return None

        away_team = teams[0].strip()
        home_team = teams[1].strip()

        # Get team codes
        away_code = normalize_team_name(away_team, 'kalshi') or away_team
        home_code = normalize_team_name(home_team, 'kalshi') or home_team

        # Extract game identifier from ticker
        # Ticker format: KXNBAGAME-25DEC03MIADAL-MIA
        parts = ticker.split('-')
        if len(parts) < 3:
            return None

        game_id = parts[1]  # e.g., "25DEC03MIADAL"
        team_code = parts[2]  # e.g., "MIA" or "DAL"

        # Get probability from last_price
        last_price = market.get('last_price', 0)
        probability = last_price  # last_price is already the correct percentage
        raw_price = last_price

        game_data = {
            'game_id': game_id,
            'team_code': team_code,
            'away_team': away_team,
            'home_team': home_team,
            'away_code': away_code,
            'home_code': home_code,
            'probability': probability,
            'raw_price': raw_price,
            'sport': self._detect_sport_from_ticker(series_ticker)
        }

        return game_data

    def _process_market_for_all_sports(self, market: Dict, series_ticker: str) -> Dict:
        """
        Process a single market for any sport category
        """
        title = market.get('title', '')
        ticker = market.get('ticker', '')

        # Skip non-vs markets
        if ' vs ' not in title:
            return None

        # Clean title - remove common suffixes
        clean_title = title.replace(' Winner?', '').replace(' winner?', '').strip()

        # Extract team names
        teams = clean_title.split(' vs ')
        if len(teams) != 2:
            return None

        away_team = teams[0].strip()
        home_team = teams[1].strip()

        # Get team codes
        away_code = normalize_team_name(away_team, 'kalshi') or away_team
        home_code = normalize_team_name(home_team, 'kalshi') or home_team

        # Get outcome prices
        try:
            outcome_prices = json.loads(market.get('outcome_prices', '[]'))
            if len(outcome_prices) != 2:
                return None

            # Determine which outcome corresponds to which team
            # Use subtitle or check if team name is in the outcome
            subtitle = market.get('subtitle', '').strip()
            
            if subtitle.lower() == away_team.lower():
                away_price = float(outcome_prices[0])
                home_price = 100 - away_price
            elif subtitle.lower() == home_team.lower():
                home_price = float(outcome_prices[0])
                away_price = 100 - home_price
            else:
                # Default: assume first outcome is away team
                away_price = float(outcome_prices[0])
                home_price = float(outcome_prices[1])

            # Convert to probabilities
            away_prob = math.floor(away_price)
            home_prob = math.floor(home_price)
            remainder = 100 - (away_prob + home_prob)
            
            # Give remainder to smaller probability
            if away_price <= home_price:
                away_prob += remainder
            else:
                home_prob += remainder

            game_data = {
                'platform': 'Kalshi',
                'market_id': market.get('id'),
                'away_team': away_team,
                'home_team': home_team,
                'away_code': away_code,
                'home_code': home_code,
                'away_prob': away_prob,
                'home_prob': home_prob,
                'away_raw_price': away_price,
                'home_raw_price': home_price,
                'ticker': ticker,
                'end_date': market.get('expiry_date', ''),
                'url': f'https://kalshi.com/markets/{ticker}',
                'sport': self._detect_sport_from_ticker(series_ticker)
            }

            return game_data

        except (json.JSONDecodeError, ValueError, IndexError) as e:
            print(f"Error parsing market {ticker}: {e}")
            return None

    def _detect_sport_from_ticker(self, ticker: str) -> str:
        """Detect sport type from ticker"""
        ticker_lower = ticker.lower()
        if 'nba' in ticker_lower:
            return 'basketball'
        elif 'nfl' in ticker_lower:
            return 'football'
        elif 'nhl' in ticker_lower:
            return 'hockey'
        elif any(keyword in ticker_lower for keyword in ['cs2', 'csgo']):
            return 'cs2'
        elif 'dota' in ticker_lower:
            return 'dota2'
        elif 'lol' in ticker_lower:
            return 'lol'
        elif 'valorant' in ticker_lower:
            return 'valorant'
        elif 'esport' in ticker_lower:
            return 'other'
        else:
            return 'other'
