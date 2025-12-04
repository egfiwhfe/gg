import requests
import json
import math
import re
from typing import List, Dict, Optional

class CryptoPolymarketAPI:
    BASE_URL = "https://gamma-api.polymarket.com"
    CRYPTO_TAG_ID = "1312" # Crypto Prices
    BITCOIN_TAG_ID = "235"
    ETHEREUM_TAG_ID = "39"
    
    def __init__(self):
        self.session = requests.Session()
    
    @staticmethod
    def _normalize_crypto_question(question: str) -> str:
        """
        Normalize crypto market questions for cross-platform matching.
        Examples:
        - "Will Bitcoin be above $100,000 on December 31, 2024?" -> "BTC_100000_2024-12-31"
        - "Will ETH close above $5000 on Jan 1?" -> "ETH_5000_2025-01-01"
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
        Get crypto markets from Polymarket
        """
        all_markets = []
        
        # Fetch for Crypto Prices tag
        events = self._get_events_by_tag(self.CRYPTO_TAG_ID, limit=limit)
        
        for event in events:
            markets = self._process_crypto_event(event)
            all_markets.extend(markets)
            
        return all_markets

    def _get_events_by_tag(self, tag_id: str, limit: int = 100) -> List[Dict]:
        all_events = []
        offset = 0
        batch_size = 100
        
        print(f"Fetching Polymarket Crypto events for tag {tag_id}...")
        
        while len(all_events) < limit:
            url = f"{self.BASE_URL}/events"
            params = {
                'closed': 'false',
                'tag_id': tag_id,
                'limit': batch_size,
                'offset': offset
            }
            
            try:
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                events = response.json()
                
                if not events:
                    break
                    
                all_events.extend(events)
                offset += len(events)
                
                if len(events) < batch_size:
                    break
                    
            except requests.RequestException as e:
                print(f"Error fetching batch at offset {offset}: {e}")
                break
                
        return all_events

    def _process_crypto_event(self, event: Dict) -> List[Dict]:
        processed_markets = []
        title = event.get('title', '')
        slug = event.get('slug', '')
        
        # We only care about markets inside the event
        for market in event.get('markets', []):
            try:
                question = market.get('question', '')
                
                # Filter for Bitcoin/Ethereum if needed, or take all "Price" markets
                if not ('Bitcoin' in title or 'Ethereum' in title or 'BTC' in title or 'ETH' in title):
                     continue
                
                # Check if it is a Yes/No market (Binary)
                outcomes = json.loads(market.get('outcomes', '[]'))
                if len(outcomes) != 2 or 'Yes' not in outcomes or 'No' not in outcomes:
                    continue

                prices = json.loads(market.get('outcomePrices', '[]'))
                if len(prices) != 2:
                    continue

                # Map Yes/No to Home/Away
                # Usually Yes is Home, No is Away in this schema adaptation
                # Or better: "Yes" is the 'home' outcome, "No" is the 'away' outcome.
                
                yes_index = outcomes.index('Yes')
                no_index = outcomes.index('No')
                
                yes_price = float(prices[yes_index]) * 100
                no_price = float(prices[no_index]) * 100
                
                # Normalize probabilities
                floor_yes = math.floor(yes_price)
                floor_no = math.floor(no_price)
                remainder = 100 - (floor_yes + floor_no)
                
                if yes_price <= no_price:
                    final_yes = floor_yes + remainder
                    final_no = floor_no
                else:
                    final_yes = floor_yes
                    final_no = floor_no + remainder
                
                # Construct "game" object
                # Use market question as the "match" identifier
                # To be compatible with "Away @ Home" key, we need unique codes.
                # For crypto, "No" vs "Yes".
                
                # Create a pseudo-team code
                # e.g. BTC_100K_DEC31
                market_id = market.get('id')
                
                # Use a sanitized version of the question as the "Home Team" (The Proposition)
                # And "No" as the "Away Team" (Against the Proposition)
                
                # But to match with Kalshi, we need them to have the SAME codes.
                # This is the hard part. matching specific markets across platforms.
                # Kalshi: "Bitcoin price > 100k"
                # Polymarket: "Bitcoin > 100k by Dec 31?"
                
                # If we cannot match them easily, maybe we just list them?
                # The user requirement is "add more markets", not necessarily "enable arbitrage for crypto".
                # However, the system is designed for arbitrage.
                # If I just add them, they will appear in the list.
                
                # For now, I will create unique codes based on the question to allow them to exist in the system.
                # If they happen to match, great.
                
                # Normalize the question for matching
                normalized_key = self._normalize_crypto_question(question)
                
                # Create human-readable team names
                yes_team = f"✓ {question}"
                no_team = f"✗ {question}"
                
                game_data = {
                    'platform': 'Polymarket',
                    'market_id': market_id,
                    'away_team': no_team,
                    'home_team': yes_team,
                    'away_code': f"NO_{normalized_key}" if normalized_key else f"NO_{market_id}",
                    'home_code': f"YES_{normalized_key}" if normalized_key else f"YES_{market_id}",
                    'away_prob': final_no,
                    'home_prob': final_yes,
                    'away_raw_price': no_price,
                    'home_raw_price': yes_price,
                    'slug': slug,
                    'end_date': market.get('endDate', ''),
                    'start_date': event.get('startDate', ''),
                    'url': f'https://polymarket.com/event/{slug}',
                    'sport': 'CRYPTO',
                    'title': question,
                    'question': question,
                    'normalized_key': normalized_key
                }
                
                processed_markets.append(game_data)
                
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing market data for {title}: {e}")
                continue
                
        return processed_markets
