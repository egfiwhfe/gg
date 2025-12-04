"""
General Markets API for Polymarket and Kalshi
Supports: Soccer, Esports, Politics, Entertainment, Economics, etc.
"""

import requests
import json
import math
import re
from typing import List, Dict, Optional

class GeneralPolymarketAPI:
    BASE_URL = "https://gamma-api.polymarket.com"
    
    # Tag IDs for various market categories
    MARKET_TAGS = {
        'SOCCER': ['102367', '102366', '100780'],  # Soccer, EPL, UEFA
        'ESPORTS': ['64', '65', '102374', '102375', '102376'],  # Esports, Dota, LoL, CS:GO
        'POLITICS': ['12', '13', '14'],  # Politics tags
        'ENTERTAINMENT': ['21', '22'],  # Entertainment tags
        'SPORTS_GENERAL': ['450'],  # General sports
        'MLB': ['102368'],  # Baseball
        'MMA': ['102369'],  # MMA
        'TENNIS': ['102371'],  # Tennis
        'GOLF': ['102372'],  # Golf
    }
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_markets_by_category(self, category: str, limit: int = 50) -> List[Dict]:
        """
        Get markets from a specific category
        Category can be: SOCCER, ESPORTS, POLITICS, ENTERTAINMENT, etc.
        """
        tag_ids = self.MARKET_TAGS.get(category.upper(), [])
        if not tag_ids:
            print(f"Unknown category: {category}")
            return []
        
        all_markets = []
        for tag_id in tag_ids[:2]:  # Limit to first 2 tags to avoid too many requests
            events = self._get_events_by_tag(tag_id, limit=limit // len(tag_ids))
            for event in events:
                markets = self._process_event(event, category.upper())
                all_markets.extend(markets)
        
        return all_markets[:limit]
    
    def _get_events_by_tag(self, tag_id: str, limit: int = 50) -> List[Dict]:
        """Get events by tag ID"""
        all_events = []
        offset = 0
        batch_size = 50
        
        print(f"Fetching Polymarket {tag_id} events...")
        
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
                print(f"Error fetching events for tag {tag_id}: {e}")
                break
        
        return all_events
    
    def _process_event(self, event: Dict, category: str) -> List[Dict]:
        """Process event into market format"""
        processed_markets = []
        title = event.get('title', '')
        slug = event.get('slug', '')
        
        for market in event.get('markets', []):
            try:
                question = market.get('question', '')
                
                # Check if it's a binary market
                outcomes = json.loads(market.get('outcomes', '[]'))
                if len(outcomes) != 2:
                    continue
                
                prices = json.loads(market.get('outcomePrices', '[]'))
                if len(prices) != 2:
                    continue
                
                # Detect if it's a Yes/No market or Team A vs Team B
                is_yes_no = 'Yes' in outcomes and 'No' in outcomes
                
                if is_yes_no:
                    yes_index = outcomes.index('Yes')
                    no_index = outcomes.index('No')
                    
                    yes_price = float(prices[yes_index]) * 100
                    no_price = float(prices[no_index]) * 100
                    
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
                    
                    # Create market identifier
                    market_id = market.get('id')
                    normalized_key = self._normalize_question(question, category)
                    
                    game_data = {
                        'platform': 'Polymarket',
                        'market_id': market_id,
                        'away_team': f"✗ {question}",
                        'home_team': f"✓ {question}",
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
                        'sport': category,
                        'title': question,
                        'question': question,
                        'normalized_key': normalized_key
                    }
                    
                    processed_markets.append(game_data)
                else:
                    # Team A vs Team B format
                    team_a = outcomes[0]
                    team_b = outcomes[1]
                    
                    price_a = float(prices[0]) * 100
                    price_b = float(prices[1]) * 100
                    
                    # Normalize
                    floor_a = math.floor(price_a)
                    floor_b = math.floor(price_b)
                    remainder = 100 - (floor_a + floor_b)
                    
                    if price_a <= price_b:
                        final_a = floor_a + remainder
                        final_b = floor_b
                    else:
                        final_a = floor_a
                        final_b = floor_b + remainder
                    
                    # Create team codes
                    market_id = market.get('id')
                    code_a = self._create_team_code(team_a)
                    code_b = self._create_team_code(team_b)
                    
                    game_data = {
                        'platform': 'Polymarket',
                        'market_id': market_id,
                        'away_team': team_a,
                        'home_team': team_b,
                        'away_code': code_a,
                        'home_code': code_b,
                        'away_prob': final_a,
                        'home_prob': final_b,
                        'away_raw_price': price_a,
                        'home_raw_price': price_b,
                        'slug': slug,
                        'end_date': market.get('endDate', ''),
                        'start_date': event.get('startDate', ''),
                        'url': f'https://polymarket.com/event/{slug}',
                        'sport': category,
                        'title': question,
                        'question': question
                    }
                    
                    processed_markets.append(game_data)
                    
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing market data: {e}")
                continue
        
        return processed_markets
    
    @staticmethod
    def _normalize_question(question: str, category: str) -> str:
        """Normalize question for cross-platform matching"""
        if not question:
            return ""
        
        # Remove special characters and normalize
        normalized = re.sub(r'[^\w\s]', '', question.lower())
        normalized = re.sub(r'\s+', '_', normalized.strip())
        
        # Truncate if too long
        if len(normalized) > 100:
            normalized = normalized[:100]
        
        return f"{category}_{normalized}"
    
    @staticmethod
    def _create_team_code(team_name: str) -> str:
        """Create a short code from team name"""
        if not team_name:
            return "UNKNOWN"
        
        # Remove special characters
        cleaned = re.sub(r'[^\w\s]', '', team_name)
        
        # Take first 3 letters of each word, uppercase
        words = cleaned.split()
        if len(words) >= 2:
            code = ''.join([w[:3].upper() for w in words[:2]])
        else:
            code = cleaned[:6].upper()
        
        return code


class GeneralKalshiAPI:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    
    # Series tickers for various categories
    MARKET_SERIES = {
        'SOCCER': ['KXEPL', 'KXUCL', 'KXWC'],  # EPL, Champions League, World Cup
        'ESPORTS': ['KXLOL', 'KXDOTA', 'KXCS'],  # LoL, Dota, CS:GO
        'POLITICS': ['KXPRES', 'KXSEN', 'KXGOV'],  # President, Senate, Governor
        'ENTERTAINMENT': ['KXOSCAR', 'KXEMMY'],  # Oscars, Emmys
    }
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_markets_by_category(self, category: str, limit: int = 50) -> List[Dict]:
        """Get markets from a specific category"""
        series_tickers = self.MARKET_SERIES.get(category.upper(), [])
        if not series_tickers:
            print(f"No series tickers for category: {category}")
            return []
        
        all_markets = []
        for ticker in series_tickers[:2]:  # Limit to avoid too many requests
            markets = self._get_markets_by_ticker(ticker, limit=limit // len(series_tickers))
            for market in markets:
                processed = self._process_market(market, category.upper())
                if processed:
                    all_markets.append(processed)
        
        return all_markets[:limit]
    
    def _get_markets_by_ticker(self, series_ticker: str, limit: int = 50) -> List[Dict]:
        """Get markets by series ticker"""
        all_markets = []
        cursor = None
        batch_size = 50
        
        print(f"Fetching Kalshi {series_ticker} markets...")
        
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
                print(f"Error fetching Kalshi markets for {series_ticker}: {e}")
                break
        
        return all_markets
    
    def _process_market(self, market: Dict, category: str) -> Optional[Dict]:
        """Process Kalshi market into standard format"""
        try:
            ticker = market.get('ticker', '')
            title = market.get('title', '')
            
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
            
            normalized_key = GeneralPolymarketAPI._normalize_question(title, category)
            
            game_data = {
                'platform': 'Kalshi',
                'market_id': ticker,
                'away_team': f"✗ {title}",
                'home_team': f"✓ {title}",
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
                'sport': category,
                'title': title,
                'question': title,
                'normalized_key': normalized_key
            }
            
            return game_data
            
        except Exception as e:
            print(f"Error processing Kalshi market {market.get('ticker')}: {e}")
            return None
