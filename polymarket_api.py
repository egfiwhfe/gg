import requests
import json
import math
from typing import List, Dict, Optional
from team_mapping import normalize_team_name as normalize_nba
try:
    from nfl_team_mapping import normalize_team_name as normalize_nfl
except ImportError:
    normalize_nfl = lambda x, y: None
try:
    from nhl_team_mapping import normalize_team_name as normalize_nhl
except ImportError:
    normalize_nhl = lambda x, y: None
try:
    from football_team_mapping import normalize_team_name as normalize_football
except ImportError:
    normalize_football = lambda x, y: None

def normalize_team_name(name, platform='polymarket'):
    # Try all normalizers
    code = normalize_nba(name, platform)
    if code: return code
    code = normalize_nfl(name, platform)
    if code: return code
    code = normalize_nhl(name, platform)
    if code: return code
    code = normalize_football(name, platform)
    if code: return code
    return None

class PolymarketAPI:
    BASE_URL = "https://gamma-api.polymarket.com"
    NBA_TAG_ID = "745"
    # Additional sports tags for broader coverage
    # Expanded tags for better market coverage:
    # 64: Esports, 65: Esports, 450: Sports, 745: NBA, 899: NFL, 
    # 100350: NHL, 102366: EPL, 100780: UEFA, 101672: NBA, 
    # 101673: NFL, 101674: NHL, 102367: Soccer, 102368: MLB,
    # 102369: MMA, 102370: Boxing, 102371: Tennis, 102372: Golf,
    # 102373: Motorsports, 102374: Dota, 102375: LoL, 102376: CS:GO
    SPORTS_TAGS = ["64", "65", "450", "745", "899", "100350", "102366", "100780", "101672", 
                   "101673", "101674", "102367", "102368", "102369", "102370", "102371", 
                   "102372", "102373", "102374", "102375", "102376", "103000", "103001"]

    def __init__(self):
        self.session = requests.Session()

    def get_market(self, market_id: str) -> Dict:
        """Get market details by ID"""
        url = f"{self.BASE_URL}/markets/{market_id}"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching market {market_id}: {e}")
            return {}

    def get_events_by_tag(self, tag_id: str, limit: int = 100) -> List[Dict]:
        """
        Get events from Polymarket filtered by tag ID
        """
        all_events = []
        offset = 0
        batch_size = 100

        print(f"Fetching Polymarket events for tag {tag_id}...")

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

                print(f"Fetched {len(all_events)} events for tag {tag_id}...")

                if len(events) < batch_size:
                    break

            except requests.RequestException as e:
                print(f"Error fetching batch at offset {offset}: {e}")
                break

        return all_events

    def get_all_events(self, limit: int = 500) -> List[Dict]:
        """
        Get all active events from Polymarket
        
        Args:
            limit: Maximum number of events to fetch
            
        Returns:
            List of all event dictionaries
        """
        all_events = []
        offset = 0
        batch_size = 100
        
        print("Fetching all Polymarket events...")
        
        while len(all_events) < limit:
            url = f"{self.BASE_URL}/events"
            params = {
                'closed': 'false',
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
                
                print(f"Fetched {len(all_events)} events so far...")
                
                if len(events) < batch_size:
                    break
                    
            except requests.RequestException as e:
                print(f"Error fetching batch at offset {offset}: {e}")
                break
                
        return all_events

    def get_nba_games(self, date_filter: Optional[str] = None) -> List[Dict]:
        """
        Get NBA games from Polymarket

        Args:
            date_filter: Optional date string in format 'YYYY-MM-DD' to filter games

        Returns:
            List of game dictionaries with standardized format
        """
        # Fetch events filtered by NBA tag
        events = self.get_events_by_tag(self.NBA_TAG_ID, limit=500)

        games = []
        for event in events:
            # Check if event has NBA tag (double check, though API should filter it)
            has_nba_tag = False
            for tag in event.get('tags', []):
                if str(tag.get('id', '')) == self.NBA_TAG_ID:
                    has_nba_tag = True
                    break
            
            if not has_nba_tag:
                continue

            title = event.get('title', '')
            slug = event.get('slug', '')

            # Filter for game events (contains 'vs.')
            if ' vs. ' not in title:
                continue

            # Optional date filtering
            if date_filter and date_filter not in slug:
                continue

            # Extract team names
            teams = title.split(' vs. ')
            if len(teams) != 2:
                continue

            away_team = teams[0].strip()
            home_team = teams[1].strip()

            # Get team codes
            away_code = normalize_team_name(away_team, 'polymarket')
            home_code = normalize_team_name(home_team, 'polymarket')

            if not away_code or not home_code:
                # print(f"Warning: Could not normalize teams: {away_team} vs {home_team}")
                continue

            # Find the Game Winner market (moneyline)
            # The moneyline market has question exactly equal to the event title
            winner_market = None
            for market in event.get('markets', []):
                question = market.get('question', '')
                if question == title:
                    winner_market = market
                    break

            # Fallback: if not found, try to find one with "Moneyline" that's NOT "1H Moneyline"
            if not winner_market:
                for market in event.get('markets', []):
                    question = market.get('question', '')
                    if 'Moneyline' in question and '1H' not in question:
                        winner_market = market
                        break

            if not winner_market:
                continue

            # Parse outcomes and prices
            try:
                import math
                outcomes = json.loads(winner_market.get('outcomes', '[]'))
                prices = json.loads(winner_market.get('outcomePrices', '[]'))

                if len(outcomes) != 2 or len(prices) != 2:
                    continue

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
                    continue

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

                game_data = {
                    'platform': 'Polymarket',
                    'market_id': winner_market.get('id'),
                    'away_team': away_team,
                    'home_team': home_team,
                    'away_code': away_code,
                    'home_code': home_code,
                    'away_prob': probs.get(away_code, 0),
                    'home_prob': probs.get(home_code, 0),
                    'away_raw_price': raw_probs.get(away_code, 0),
                    'home_raw_price': raw_probs.get(home_code, 0),
                    'slug': slug,
                    'end_date': winner_market.get('endDate', ''),
                    'start_date': event.get('startDate', ''),
                    'url': f'https://polymarket.com/event/{slug}',
                }

                games.append(game_data)

            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing market data for {title}: {e}")
                continue

        return games

    def get_today_games(self) -> List[Dict]:
        """Get today's NBA games"""
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        return self.get_nba_games(date_filter=today)

    def get_all_sports_games(self) -> List[Dict]:
        """
        Get games from all sports categories for broader market coverage
        Expanded limits to ensure we meet minimum requirements
        """
        all_games = []
        seen_events = set()  # Avoid duplicates

        for tag_id in self.SPORTS_TAGS:
            try:
                # Increased limit from 300 to 500 for better coverage
                events = self.get_events_by_tag(tag_id, limit=500)
                for event in events:
                    event_id = event.get('id')
                    if event_id in seen_events:
                        continue
                    seen_events.add(event_id)

                    # Process similar to get_nba_games but for all sports
                    games = self._process_event_for_all_sports(event)
                    all_games.extend(games)

            except Exception as e:
                print(f"Error processing tag {tag_id}: {e}")
                continue

        print(f"Total Polymarket games collected: {len(all_games)}")
        return all_games

    def _process_event_for_all_sports(self, event: Dict) -> List[Dict]:
        """
        Process a single event for any sport category
        """
        games = []
        title = event.get('title', '')
        slug = event.get('slug', '')

        # Skip if not a vs match
        if ' vs ' not in title and ' vs. ' not in title:
            return games

        # Common prefixes to strip
        prefixes_to_strip = ['NBA:', 'NFL:', 'NHL:', 'EPL:', 'LoL:', 'CS2:', 'Dota 2:', 'Valorant:', 'MLB:']
        clean_title = title
        for prefix in prefixes_to_strip:
            if clean_title.startswith(prefix):
                clean_title = clean_title[len(prefix):].strip()
                break

        # Extract team names
        separator = ' vs. ' if ' vs. ' in clean_title else ' vs '
        teams = clean_title.split(separator)
        if len(teams) != 2:
            return games

        away_team = teams[0].strip()
        home_team = teams[1].strip()

        # Get team codes
        away_code = normalize_team_name(away_team, 'polymarket')
        home_code = normalize_team_name(home_team, 'polymarket')

        if not away_code or not home_code:
            # For less common sports, use team names as codes
            away_code = away_team
            home_code = home_team

        # Find the primary winner market
        winner_market = None
        for market in event.get('markets', []):
            question = market.get('question', '')
            # Exact match with cleaned title or original title
            if question == clean_title or question == title:
                winner_market = market
                break
            # Fallback to winner/moneyline markets
            if ('Winner' in question or 'Moneyline' in question) and '1H' not in question and 'Map' not in question:
                if not winner_market:  # Take first match
                    winner_market = market

        if not winner_market:
            return games

        # Parse outcomes and prices
        try:
            outcomes = json.loads(winner_market.get('outcomes', '[]'))
            prices = json.loads(winner_market.get('outcomePrices', '[]'))

            if len(outcomes) != 2 or len(prices) != 2:
                return games

            # Process outcomes
            outcome_data = []
            for outcome, price in zip(outcomes, prices):
                team_code = normalize_team_name(outcome, 'polymarket') or outcome
                outcome_data.append({
                    'code': team_code,
                    'raw_prob': float(price) * 100
                })

            if len(outcome_data) != 2:
                return games

            # Normalize probabilities
            prob1 = outcome_data[0]['raw_prob']
            prob2 = outcome_data[1]['raw_prob']
            floor1 = math.floor(prob1)
            floor2 = math.floor(prob2)
            remainder = 100 - (floor1 + floor2)

            # Give remainder to smaller probability
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

            game_data = {
                'platform': 'Polymarket',
                'market_id': winner_market.get('id'),
                'away_team': away_team,
                'home_team': home_team,
                'away_code': away_code,
                'home_code': home_code,
                'away_prob': probs.get(away_code, 0),
                'home_prob': probs.get(home_code, 0),
                'away_raw_price': raw_probs.get(away_code, 0),
                'home_raw_price': raw_probs.get(home_code, 0),
                'slug': slug,
                'end_date': winner_market.get('endDate', ''),
                'start_date': event.get('startDate', ''),
                'url': f'https://polymarket.com/event/{slug}',
                'sport': self._detect_sport_from_title(title)
            }

            games.append(game_data)

        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing market data for {title}: {e}")

        return games

    def _detect_sport_from_title(self, title: str) -> str:
        """
        Enhanced sport detection using multiple methods:
        1. Team name mapping (most reliable)
        2. Title prefixes
        3. Title keywords
        """
        title_lower = title.lower()
        
        # Extract team names from title
        away_team, home_team = self._extract_teams_from_title(title)
        
        # Method 1: Use team mapping to detect sport (most reliable)
        if away_team and home_team:
            away_team_lower = away_team.lower()
            home_team_lower = home_team.lower()
            
            # Check NBA teams
            nba_teams = self._get_nba_team_list()
            if (away_team_lower in nba_teams or home_team_lower in nba_teams):
                return 'basketball'
            
            # Check NFL teams  
            nfl_teams = self._get_nfl_team_list()
            if (away_team_lower in nfl_teams or home_team_lower in nfl_teams):
                return 'football'
                
            # Check NHL teams
            nhl_teams = self._get_nhl_team_list()
            if (away_team_lower in nhl_teams or home_team_lower in nhl_teams):
                return 'hockey'
        
        # Method 2: Check for sport prefixes in title
        if any(keyword in title_lower for keyword in ['nba:', 'basketball']):
            return 'basketball'
        elif any(keyword in title_lower for keyword in ['nfl:', 'football']):
            return 'football'
        elif any(keyword in title_lower for keyword in ['nhl:', 'hockey']):
            return 'hockey'
        elif any(keyword in title_lower for keyword in ['lol:', 'league of legends']):
            return 'lol'
        elif any(keyword in title_lower for keyword in ['dota 2:', 'dota']):
            return 'dota2'
        elif any(keyword in title_lower for keyword in ['cs2:', 'counter-strike']):
            return 'cs2'
        elif any(keyword in title_lower for keyword in ['valorant:']):
            return 'valorant'
        elif any(keyword in title_lower for keyword in ['esports:', 'esport']):
            return 'other'
        else:
            # Method 3: Infer from common team name patterns
            if self._contains_esports_indicators(title):
                return 'other'  # Esports
            elif self._contains_traditional_sports_indicators(title):
                # Try to determine which traditional sport
                if any(word in title_lower for word in ['basketball', 'hoops']):
                    return 'basketball'
                elif any(word in title_lower for word in ['football', 'qb', 'touchdown']):
                    return 'football'
                elif any(word in title_lower for word in ['hockey', 'puck', 'goalie']):
                    return 'hockey'
            
            return 'other'
    
    def _extract_teams_from_title(self, title):
        """Extract away and home team names from title"""
        # Remove common prefixes
        prefixes_to_strip = ['NBA:', 'NFL:', 'NHL:', 'EPL:', 'LoL:', 'CS2:', 'Dota 2:', 'Valorant:', 'MLB:']
        clean_title = title
        for prefix in prefixes_to_strip:
            if clean_title.startswith(prefix):
                clean_title = clean_title[len(prefix):].strip()
                break
        
        # Split by 'vs' or 'vs.'
        separator = ' vs. ' if ' vs. ' in clean_title else ' vs '
        if separator in clean_title:
            teams = clean_title.split(separator)
            if len(teams) == 2:
                return teams[0].strip(), teams[1].strip()
        
        return None, None
    
    def _contains_esports_indicators(self, title):
        """Check if title contains esports indicators"""
        esports_keywords = ['lol', 'dota', 'valorant', 'cs2', 'counter-strike', 'league of legends', 
                          'overwatch', 'rocket league', 'fifa', 'esports', 'gaming']
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in esports_keywords)
    
    def _contains_traditional_sports_indicators(self, title):
        """Check if title contains traditional sports indicators"""
        traditional_keywords = ['basketball', 'football', 'hockey', 'baseball', 'soccer', 
                             'tennis', 'golf', 'boxing', 'mma']
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in traditional_keywords)
    
    def _get_nba_team_list(self):
        """Get list of NBA team names for detection"""
        return ['lakers', 'warriors', 'celtics', 'heat', 'nets', 'bucks', 'nuggets', 'suns',
                '76ers', 'knicks', 'clippers', 'mavericks', 'grizzlies', 'timberwolves', 
                'pelicans', 'kings', 'trail blazers', 'jazz', 'thunder',
                'rockets', 'spurs', 'pacers', 'bulls', 'cavaliers', 'pistons', 'hornets',
                'magic', 'wizards', 'hawks', 'raptors', 'pacers', 'blazers', 'warriors',
                'golden state warriors', 'los angeles lakers', 'boston celtics', 'miami heat',
                'brooklyn nets', 'milwaukee bucks', 'denver nuggets', 'phoenix suns']
    
    def _get_nfl_team_list(self):
        """Get list of NFL team names for detection"""
        return ['chiefs', 'bengals', 'bills', 'dolphins', 'patriots', 'jets', 'ravens', 
                'steelers', 'texans', 'colts', 'jaguars', 'titans', 'broncos', 'raiders',
                'chargers', 'browns', 'bears', 'lions', 'packers', 'vikings', 'cowboys',
                'giants', 'eagles', 'redskins', 'falcons', 'panthers', 'saints', 'buccaneers',
                'cardinals', 'rams', '49ers', 'seahawks']
    
    def _get_nhl_team_list(self):
        """Get list of NHL team names for detection"""
        return ['bruins', 'sabres', 'red wings', 'panthers', 'canadiens', 'senators',
                'lightning', 'maple leafs', 'hurricanes', 'blue jackets', 'rangers',
                'islanders', 'flyers', 'penguins', 'capitals', 'blackhawks', 'avalanche',
                'stars', 'wild', 'predators', 'blues', 'jets', 'ducks', 'coyotes',
                'oilers', 'kings', 'sharks', 'knights', 'canucks', 'golden knights']
