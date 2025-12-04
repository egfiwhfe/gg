import requests
import json
import math
import re
from typing import List, Dict

class CryptoKalshiAPI:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    CRYPTO_TICKERS = ["KXBTC", "KXETH"]
    
    def __init__(self):
        self.session = requests.Session()
    
    @staticmethod
    def _normalize_crypto_question(question: str) -> str:
        """
        Normalize crypto market questions for cross-platform matching.
        This should match the logic in CryptoPolymarketAPI._normalize_crypto_question
        """
        if not question:
            return ""
        
        # Normalize text
        q = question.lower().strip()
        
        # Extract crypto symbol
        crypto = None
        if 'bitcoin' in q or 'btc' in q:
            crypto = 'BTC'
        elif 'ethereum' in q or 'eth' in q:
            crypto = 'ETH'
        elif 'solana' in q or 'sol' in q:
            crypto = 'SOL'
        elif 'cardano' in q or 'ada' in q:
            crypto = 'ADA'
        elif 'dogecoin' in q or 'doge' in q:
            crypto = 'DOGE'
        
        if not crypto:
            # Fallback: use first word
            words = q.split()
            crypto = words[0].upper() if words else 'CRYPTO'
        
        # Extract price threshold
        price_match = re.search(r'\$?(\d+[,\d]*k?)', q)
        price = None
        if price_match:
            price_str = price_match.group(1).replace(',', '')
            if 'k' in price_str.lower():
                price = int(float(price_str.lower().replace('k', '')) * 1000)
            else:
                price = int(price_str)
        
        # Extract date
        date_patterns = [
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # 2024-12-31
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # 12/31/2024
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s*(\d{4})?',
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s+(\d{1,2}),?\s*(\d{4})?'
        ]
        
        date = None
        for pattern in date_patterns:
            match = re.search(pattern, q)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    if groups[0].isalpha():
                        # Month name format
                        month_map = {
                            'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
                            'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
                            'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
                            'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
                            'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
                            'december': 12, 'dec': 12
                        }
                        month = month_map.get(groups[0].lower(), 1)
                        day = int(groups[1])
                        year = int(groups[2]) if groups[2] else 2024
                        date = f"{year:04d}-{month:02d}-{day:02d}"
                    else:
                        # Numeric format
                        if '-' in match.group(0):
                            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                        else:
                            month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                        date = f"{year:04d}-{month:02d}-{day:02d}"
                break
        
        # Extract direction (above/below)
        direction = 'ABOVE'
        if 'below' in q or 'under' in q or 'less than' in q:
            direction = 'BELOW'
        
        # Build normalized key
        parts = [crypto]
        if direction:
            parts.append(direction)
        if price:
            parts.append(str(price))
        if date:
            parts.append(date)
        
        return '_'.join(parts)

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
            
            # Normalize the question for matching
            normalized_key = self._normalize_crypto_question(title)
            
            # Create human-readable team names
            yes_team = f"✓ {title}"
            no_team = f"✗ {title}"
            
            game_data = {
                'platform': 'Kalshi',
                'market_id': ticker,
                'away_team': no_team,
                'home_team': yes_team,
                'away_code': f"NO_{normalized_key}" if normalized_key else f"NO_{ticker}",
                'home_code': f"YES_{normalized_key}" if normalized_key else f"YES_{ticker}",
                'away_prob': final_no,
                'home_prob': final_yes,
                'away_raw_price': no_price,
                'home_raw_price': yes_price,
                'ticker': ticker,
                'away_ticker': ticker,
                'home_ticker': ticker,
                'end_date': market.get('close_time', ''),
                'url': f'https://kalshi.com/markets/{ticker}',
                'sport': 'CRYPTO',
                'title': title,
                'question': title,
                'normalized_key': normalized_key
            }
            
            return game_data
            
        except Exception as e:
            print(f"Error processing Kalshi crypto market {market.get('ticker')}: {e}")
            return None
