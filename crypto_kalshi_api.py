import requests
import json
import math
from typing import List, Dict

class CryptoKalshiAPI:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    CRYPTO_TICKERS = ["KXBTC", "KXETH"]
    
    def __init__(self):
        self.session = requests.Session()

    def get_crypto_markets(self, limit: int = 100) -> List[Dict]:
        """
        Get crypto markets from Kalshi
        """
        all_markets = []
        
        for ticker in self.CRYPTO_TICKERS:
            markets = self._get_markets_by_ticker(ticker, limit=limit)
            for market in markets:
                processed = self._process_market(market)
                if processed:
                    all_markets.append(processed)
                    
        return all_markets

    def _get_markets_by_ticker(self, series_ticker: str, limit: int = 100) -> List[Dict]:
        all_markets = []
        cursor = None
        batch_size = 100
        
        print(f"Fetching Kalshi Crypto markets for series {series_ticker}...")
        
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

                if not cursor or len(markets) < batch_size:
                    break

            except requests.RequestException as e:
                print(f"Error fetching batch: {e}")
                break

        return all_markets

    def _process_market(self, market: Dict) -> Dict:
        try:
            ticker = market.get('ticker', '')
            title = market.get('title', '')
            
            # Use last_price as probability for Yes
            last_price = market.get('last_price', 0)
            yes_price = last_price
            no_price = 100 - yes_price
            
            # Normalize
            floor_yes = math.floor(yes_price)
            floor_no = math.floor(no_price)
            remainder = 100 - (floor_yes + floor_no)
            
            if yes_price <= no_price:
                final_yes = floor_yes + remainder
                final_no = floor_no
            else:
                final_yes = floor_yes
                final_no = floor_no + remainder
                
            # Construct game data
            # Use Yes/No
            
            game_data = {
                'platform': 'Kalshi',
                'market_id': ticker, # ticker is unique ID in Kalshi
                'away_team': f"No: {title}",
                'home_team': f"Yes: {title}",
                'away_code': f"NO_{ticker}",
                'home_code': f"YES_{ticker}",
                'away_prob': final_no,
                'home_prob': final_yes,
                'away_raw_price': no_price,
                'home_raw_price': yes_price,
                'ticker': ticker,
                'end_date': market.get('close_time', ''), # or expiry_date
                'url': f'https://kalshi.com/markets/{ticker}',
                'sport': 'CRYPTO',
                'title': title
            }
            
            return game_data
            
        except Exception as e:
            print(f"Error processing Kalshi crypto market {market.get('ticker')}: {e}")
            return None
