#!/usr/bin/env python3
"""
Flask API for PolyMix monitoring
Provides real-time NBA odds comparison data
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from datetime import datetime, timedelta
from polymarket_api import PolymarketAPI
from kalshi_api import KalshiAPI
from mock_kalshi_api import get_kalshi_api
from team_mapping import TEAM_LOGOS
from nfl_polymarket_api import NFLPolymarketAPI
from nfl_kalshi_api import NFLKalshiAPI
from nfl_team_mapping import NFL_TEAM_LOGOS
from nhl_polymarket_api import NHLPolymarketAPI
from nhl_kalshi_api import NHLKalshiAPI
from nhl_team_mapping import NHL_TEAM_LOGOS
from football_polymarket_api import FootballPolymarketAPI
from football_kalshi_api import FootballKalshiAPI
from football_team_mapping import FOOTBALL_TEAM_LOGOS
from odds_api_aggregator import OddsAPIAggregator
from manifold_api import ManifoldAPI
from config import PLATFORMS
import os
import json
from collections import defaultdict, deque
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from paper_trading import PaperTradingSystem
from pushplus_notifier import PushPlusNotifier
import atexit

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# Initialize subsystems
paper_trader = PaperTradingSystem()
notifier = PushPlusNotifier()
scheduler = BackgroundScheduler()

# Shared fee/slippage assumptions so every consumer evaluates
# opportunities with identical math
POLYMARKET_FEE = 0.02  # 2% Polymarket fee
KALSHI_FEE = 0.07      # 7% Kalshi fee
SLIPPAGE_ESTIMATE = 0.005  # 0.5% slippage allowance

# Cache data to avoid too frequent API calls
nba_cache = {
    'data': None,
    'timestamp': None,
    'cache_duration': 30  # Cache for 30 seconds
}

nfl_cache = {
    'data': None,
    'timestamp': None,
    'cache_duration': 30  # Cache for 30 seconds
}

nhl_cache = {
    'data': None,
    'timestamp': None,
    'cache_duration': 30
}

football_cache = {
    'data': None,
    'timestamp': None,
    'cache_duration': 30
}


# Historical data storage (keep last 60 data points = 30 minutes at 30s intervals)
nba_game_history = defaultdict(lambda: {
    'diff_history': deque(maxlen=60),
    'poly_history': deque(maxlen=60),
    'kalshi_history': deque(maxlen=60),
    'timestamps': deque(maxlen=60)
})

nfl_game_history = defaultdict(lambda: {
    'diff_history': deque(maxlen=60),
    'poly_history': deque(maxlen=60),
    'kalshi_history': deque(maxlen=60),
    'timestamps': deque(maxlen=60)
})

nhl_game_history = defaultdict(lambda: {
    'diff_history': deque(maxlen=60),
    'poly_history': deque(maxlen=60),
    'kalshi_history': deque(maxlen=60),
    'timestamps': deque(maxlen=60)
})

football_game_history = defaultdict(lambda: {
    'diff_history': deque(maxlen=60),
    'poly_history': deque(maxlen=60),
    'kalshi_history': deque(maxlen=60),
    'timestamps': deque(maxlen=60)
})


def _extract_price_value(game, side):
    """Extract the most precise available price for a given side."""
    if not game:
        return None
    candidates = [
        f"{side}_raw_price",
        f"raw_{side}",
        f"{side}_raw",
        f"{side}_prob",
        side
    ]
    for key in candidates:
        value = game.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _pick_best_leg(poly_price, kalshi_price):
    poly_eff = poly_price * (1 + POLYMARKET_FEE + SLIPPAGE_ESTIMATE)
    kalshi_eff = kalshi_price * (1 + KALSHI_FEE + SLIPPAGE_ESTIMATE)
    if poly_eff <= kalshi_eff:
        return {
            'platform': 'Polymarket',
            'price': poly_price,
            'effective': poly_eff
        }
    return {
        'platform': 'Kalshi',
        'price': kalshi_price,
        'effective': kalshi_eff
    }


def _calculate_risk_free_details(poly_game, kalshi_game):
    """Return arbitrage metrics with identical math to paper trading."""
    poly_away = _extract_price_value(poly_game, 'away')
    poly_home = _extract_price_value(poly_game, 'home')
    kalshi_away = _extract_price_value(kalshi_game, 'away')
    kalshi_home = _extract_price_value(kalshi_game, 'home')

    if None in [poly_away, poly_home, kalshi_away, kalshi_home]:
        return None

    away_leg = _pick_best_leg(poly_away, kalshi_away)
    home_leg = _pick_best_leg(poly_home, kalshi_home)

    gross_cost = away_leg['price'] + home_leg['price']
    gross_edge = 100 - gross_cost

    total_cost = away_leg['effective'] + home_leg['effective']
    if total_cost <= 0:
        return None

    net_edge = 100 - total_cost
    roi = net_edge / total_cost
    if roi <= 0:
        return None

    return {
        'best_away_platform': away_leg['platform'],
        'best_home_platform': home_leg['platform'],
        'best_away_price': round(away_leg['price'], 4),
        'best_home_price': round(home_leg['price'], 4),
        'best_away_effective': round(away_leg['effective'], 4),
        'best_home_effective': round(home_leg['effective'], 4),
        'gross_cost': round(gross_cost, 4),
        'gross_edge': round(gross_edge, 4),
        'total_cost': round(total_cost, 4),
        'net_edge': round(net_edge, 4),
        'roi_percent': round(roi * 100, 4),
        'fees': {
            'polymarket': POLYMARKET_FEE,
            'kalshi': KALSHI_FEE,
            'slippage': SLIPPAGE_ESTIMATE
        }
    }


def _get_cached_data(cache_obj, now, force_refresh=False):
    if not force_refresh and cache_obj['data'] and cache_obj['timestamp']:
        elapsed = (now - cache_obj['timestamp']).seconds
        if elapsed < cache_obj['cache_duration']:
            return cache_obj['data']
    return None


def _set_cache_data(cache_obj, data, timestamp):
    cache_obj['data'] = data
    cache_obj['timestamp'] = timestamp


def get_date_range():
    """Get today and tomorrow's date strings"""
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    return today.strftime('%Y-%m-%d'), tomorrow.strftime('%Y-%m-%d')

def match_games(polymarket_games, kalshi_games):
    """Match games between platforms"""
    matched = []
    for poly_game in polymarket_games:
        poly_away = poly_game['away_code']
        poly_home = poly_game['home_code']

        for kalshi_game in kalshi_games:
            kalshi_away = kalshi_game['away_code']
            kalshi_home = kalshi_game['home_code']

            if poly_away == kalshi_away and poly_home == kalshi_home:
                matched.append((poly_game, kalshi_game))
                break

    return matched

def match_additional_platform(base_games, additional_games):
    """Match additional platform games to base games"""
    matched_dict = {}
    for base_game in base_games:
        game_key = f"{base_game['away_code']}@{base_game['home_code']}"
        matched_dict[game_key] = None

        for add_game in additional_games:
            if (add_game['away_code'] == base_game['away_code'] and
                add_game['home_code'] == base_game['home_code']):
                matched_dict[game_key] = add_game
                break

    return matched_dict

def calculate_comparisons(matched_games, team_logos, game_history_dict, odds_games=None, manifold_games=None):
    """Calculate odds comparisons with historical tracking and analysis"""
    comparisons = []
    current_time = datetime.now()

    # Match additional platforms if provided
    odds_dict = {}
    manifold_dict = {}

    if odds_games:
        base_games = [poly_game for poly_game, _ in matched_games]
        odds_dict = match_additional_platform(base_games, odds_games)

    if manifold_games:
        base_games = [poly_game for poly_game, _ in matched_games]
        manifold_dict = match_additional_platform(base_games, manifold_games)

    for poly_game, kalshi_game in matched_games:
        away_diff = abs(poly_game['away_prob'] - kalshi_game['away_prob'])
        home_diff = abs(poly_game['home_prob'] - kalshi_game['home_prob'])
        max_diff = max(away_diff, home_diff)

        # Extract game time from end_date
        game_time = poly_game.get('end_date', '')[:16] if poly_game.get('end_date') else ''

        # Create unique game key
        game_key = f"{poly_game['away_code']}@{poly_game['home_code']}"

        # Get historical data for this game
        history = game_history_dict[game_key]

        # Add current data to history
        history['diff_history'].append(max_diff)
        history['poly_history'].append((poly_game['away_prob'], poly_game['home_prob']))
        history['kalshi_history'].append((kalshi_game['away_prob'], kalshi_game['home_prob']))
        history['timestamps'].append(current_time.isoformat())

        # Calculate trend (comparing recent 5 points vs older 5 points)
        trend = 'stable'
        trend_value = 0
        if len(history['diff_history']) >= 10:
            recent_avg = sum(list(history['diff_history'])[-5:]) / 5
            older_avg = sum(list(history['diff_history'])[-10:-5]) / 5
            trend_value = recent_avg - older_avg
            if trend_value > 0.5:
                trend = 'increasing'
            elif trend_value < -0.5:
                trend = 'decreasing'

        # Calculate price change (current vs 5 minutes ago = ~10 data points ago)
        poly_change = {'away': 0, 'home': 0}
        kalshi_change = {'away': 0, 'home': 0}
        if len(history['poly_history']) >= 10:
            old_poly = history['poly_history'][-10]
            poly_change['away'] = round(poly_game['away_prob'] - old_poly[0], 1)
            poly_change['home'] = round(poly_game['home_prob'] - old_poly[1], 1)

            old_kalshi = history['kalshi_history'][-10]
            kalshi_change['away'] = round(kalshi_game['away_prob'] - old_kalshi[0], 1)
            kalshi_change['home'] = round(kalshi_game['home_prob'] - old_kalshi[1], 1)

        # Calculate arbitrage opportunity score (0-100)
        arb_score = 0
        # Base score from difference (0-50)
        arb_score += min(max_diff * 5, 50)
        # Bonus for increasing trend (0-20)
        if trend == 'increasing':
            arb_score += min(abs(trend_value) * 10, 20)
        # Bonus for volatility (0-15)
        if len(history['diff_history']) >= 5:
            recent_diffs = list(history['diff_history'])[-5:]
            volatility = max(recent_diffs) - min(recent_diffs)
            arb_score += min(volatility * 3, 15)
        # Bonus for high absolute difference (0-15)
        if max_diff >= 8:
            arb_score += 15
        elif max_diff >= 5:
            arb_score += 10

        arb_score = min(round(arb_score), 100)

        # Get additional platform data if available
        game_key = f"{poly_game['away_code']}@{poly_game['home_code']}"
        odds_game = odds_dict.get(game_key)
        manifold_game = manifold_dict.get(game_key)

        comparison = {
            'away_team': poly_game['away_team'],
            'home_team': poly_game['home_team'],
            'away_code': poly_game['away_code'],
            'home_code': poly_game['home_code'],
            'away_logo': team_logos.get(poly_game['away_code'], ''),
            'home_logo': team_logos.get(poly_game['home_code'], ''),
            'polymarket': {
                'away': round(poly_game['away_prob'], 1),
                'home': round(poly_game['home_prob'], 1),
                'raw_away': poly_game.get('away_raw_price', poly_game['away_prob']),
                'raw_home': poly_game.get('home_raw_price', poly_game['home_prob']),
                'url': poly_game.get('url', ''),
                'market_id': poly_game.get('market_id'),
                'away_market_id': poly_game.get('away_market_id'),
                'home_market_id': poly_game.get('home_market_id')
            },
            'kalshi': {
                'away': round(kalshi_game['away_prob'], 1),
                'home': round(kalshi_game['home_prob'], 1),
                'raw_away': kalshi_game.get('away_raw_price', kalshi_game['away_prob']),
                'raw_home': kalshi_game.get('home_raw_price', kalshi_game['home_prob']),
                'url': kalshi_game.get('url', ''),
                'away_ticker': kalshi_game.get('away_ticker'),
                'home_ticker': kalshi_game.get('home_ticker')
            },
            'odds_api': {
                'away': round(odds_game['away_prob'], 1) if odds_game else None,
                'home': round(odds_game['home_prob'], 1) if odds_game else None,
                'url': odds_game.get('url', '') if odds_game else '',
                'bookmakers': odds_game.get('bookmakers', []) if odds_game else []
            } if odds_game else None,
            'manifold': {
                'away': round(manifold_game['away_prob'], 1) if manifold_game else None,
                'home': round(manifold_game['home_prob'], 1) if manifold_game else None,
                'url': manifold_game.get('url', '') if manifold_game else ''
            } if manifold_game else None,
            'diff': {
                'away': round(away_diff, 1),
                'home': round(home_diff, 1),
                'max': round(max_diff, 1)
            },
            'trend': {
                'direction': trend,
                'value': round(trend_value, 1)
            },
            'price_change': {
                'polymarket': poly_change,
                'kalshi': kalshi_change
            },
            'arbitrage_score': arb_score,
            'game_time': game_time,
            'history': {
                'diff': list(history['diff_history']),
                'timestamps': list(history['timestamps'])
            }
        }

        comparisons.append(comparison)

    # Sort by arbitrage score (descending), then by max difference
    comparisons.sort(key=lambda x: (x['arbitrage_score'], x['diff']['max']), reverse=True)

    return comparisons


def _build_nba_payload(now):
    today, tomorrow = get_date_range()

    poly_api = PolymarketAPI()
    kalshi_api = KalshiAPI()

    poly_today = poly_api.get_nba_games(date_filter=today)
    poly_tomorrow = poly_api.get_nba_games(date_filter=tomorrow)
    poly_games = poly_today + poly_tomorrow
    kalshi_games = kalshi_api.get_nba_games()

    odds_games = []
    manifold_games = []

    if PLATFORMS.get('odds_api', {}).get('enabled', False):
        try:
            odds_api = OddsAPIAggregator()
            odds_games = odds_api.get_nba_games()
            print(f"✅ Fetched {len(odds_games)} games from Odds API")
        except Exception as e:
            print(f"⚠️  Odds API error: {e}")

    if PLATFORMS.get('manifold', {}).get('enabled', False):
        try:
            manifold_api = ManifoldAPI()
            manifold_games = manifold_api.get_nba_games()
            print(f"✅ Fetched {len(manifold_games)} games from Manifold")
        except Exception as e:
            print(f"⚠️  Manifold API error: {e}")

    matched = match_games(poly_games, kalshi_games)
    comparisons = calculate_comparisons(
        matched, TEAM_LOGOS, nba_game_history,
        odds_games=odds_games,
        manifold_games=manifold_games
    )

    today_games = []
    tomorrow_games = []
    for game in comparisons:
        game_date = game['game_time'][:10] if game['game_time'] else ''
        if game_date == today:
            today_games.append(game)
        elif game_date == tomorrow:
            tomorrow_games.append(game)

    return {
        'success': True,
        'sport': 'nba',
        'timestamp': now.isoformat(),
        'dates': {
            'today': today,
            'tomorrow': tomorrow
        },
        'stats': {
            'total_games': len(comparisons),
            'today_games': len(today_games),
            'tomorrow_games': len(tomorrow_games),
            'poly_total': len(poly_games),
            'kalshi_total': len(kalshi_games),
            'matched': len(matched)
        },
        'games': {
            'today': today_games,
            'tomorrow': tomorrow_games
        }
    }


def fetch_nba_data(force_refresh=False):
    now = datetime.now()
    cached = _get_cached_data(nba_cache, now, force_refresh)
    if cached:
        return cached
    result = _build_nba_payload(now)
    _set_cache_data(nba_cache, result, now)
    return result


def fetch_all_sports_data(force_refresh=False):
    """
    Fetch comprehensive data from all sports categories for maximum market coverage
    """
    now = datetime.now()
    
    # Create a combined cache key
    cache_key = 'all_sports'
    if not force_refresh:
        # Check if we have recent data
        try:
            with open('all_sports_cache.json', 'r') as f:
                cached = json.load(f)
                cache_time = datetime.fromisoformat(cached.get('timestamp', '1970-01-01'))
                if (now - cache_time).seconds < 15:  # 15 second cache for faster updates
                    return cached
        except:
            pass
    
    print("Fetching comprehensive sports data...")
    
    # Initialize APIs
    poly_api = PolymarketAPI()
    kalshi_api = get_kalshi_api()  # Use mock API if real API is unavailable
    
    # Get all sports games from both platforms
    poly_games = poly_api.get_all_sports_games()
    kalshi_games = kalshi_api.get_all_sports_games()
    
    print(f"Found {len(poly_games)} Polymarket games and {len(kalshi_games)} Kalshi games")
    
    # Enhanced matching with fuzzy logic
    matched_games = []
    matched_count = 0
    
    # Create a dictionary of Kalshi games for faster lookup
    kalshi_dict = {}
    for game in kalshi_games:
        key = f"{game['away_code']}@{game['home_code']}"
        kalshi_dict[key] = game
    
    # Try exact matches first
    for poly_game in poly_games:
        poly_key = f"{poly_game['away_code']}@{poly_game['home_code']}"
        if poly_key in kalshi_dict:
            matched_games.append({
                'polymarket': poly_game,
                'kalshi': kalshi_dict[poly_key],
                'match_type': 'exact'
            })
            matched_count += 1
            continue
        
        # Try fuzzy matching
        for kalshi_game in kalshi_games:
            if _fuzzy_match(poly_game, kalshi_game):
                matched_games.append({
                    'polymarket': poly_game,
                    'kalshi': kalshi_game,
                    'match_type': 'fuzzy'
                })
                matched_count += 1
                break
    
    print(f"Successfully matched {matched_count} games")
    
    # Calculate arbitrage opportunities
    arb_opportunities = []
    for match in matched_games:
        poly = match['polymarket']
        kalshi = match['kalshi']
        arb_details = _calculate_risk_free_details(poly, kalshi)
        match['risk_free_arb'] = arb_details
        if arb_details:
            arb_opportunities.append({
                'polymarket': poly,
                'kalshi': kalshi,
                'match_type': match['match_type'],
                'arb_score': arb_details['roi_percent'],
                'risk_free_arb': arb_details
            })
    
    # Transform data to homepage format for consistency
    homepage_games = []
    
    # Process matched games for homepage format
    for match in matched_games:
        poly = match['polymarket']
        kalshi = match['kalshi']
        arb_details = match.get('risk_free_arb')
        arb_score = arb_details['roi_percent'] if arb_details else 0
        
        # Calculate differences
        away_diff = abs(poly['away_prob'] - kalshi['away_prob'])
        home_diff = abs(poly['home_prob'] - kalshi['home_prob'])
        max_diff = max(away_diff, home_diff)
        
        # Extract game time
        game_time = poly.get('end_date', '')[:16] if poly.get('end_date') else ''
        
        # Get team logos (empty for now, can be enhanced later)
        away_logo = ''
        home_logo = ''
        
        homepage_game = {
            'away_team': poly['away_team'],
            'home_team': poly['home_team'],
            'away_code': poly['away_code'],
            'home_code': poly['home_code'],
            'away_logo': away_logo,
            'home_logo': home_logo,
            'sport': poly.get('sport', 'unknown'),
            'polymarket': {
                'away': round(poly['away_prob'], 1),
                'home': round(poly['home_prob'], 1),
                'raw_away': poly.get('away_raw_price', poly['away_prob']),
                'raw_home': poly.get('home_raw_price', poly['home_prob']),
                'url': poly.get('url', ''),
                'market_id': poly.get('market_id'),
                'away_market_id': poly.get('away_market_id'),
                'home_market_id': poly.get('home_market_id')
            },
            'kalshi': {
                'away': round(kalshi['away_prob'], 1),
                'home': round(kalshi['home_prob'], 1),
                'raw_away': kalshi.get('away_raw_price', kalshi['away_prob']),
                'raw_home': kalshi.get('home_raw_price', kalshi['home_prob']),
                'url': kalshi.get('url', ''),
                'away_ticker': kalshi.get('away_ticker'),
                'home_ticker': kalshi.get('home_ticker')
            },
            'diff': {
                'away': round(away_diff, 1),
                'home': round(home_diff, 1),
                'max': round(max_diff, 1)
            },
            'arbitrage_score': round(arb_score, 2) if arb_score > 0 else 0,
            'game_time': game_time,
            'match_type': match['match_type'],
            'risk_free_arb': arb_details
        }
        
        homepage_games.append(homepage_game)
    
    # Process unmatched polymarket games for homepage format
    for poly_game in poly_games:
        # Skip if already processed in matched games
        if any(poly_game['away_code'] == m['polymarket']['away_code'] and 
               poly_game['home_code'] == m['polymarket']['home_code'] for m in matched_games):
            continue
            
        game_time = poly_game.get('end_date', '')[:16] if poly_game.get('end_date') else ''
        
        homepage_game = {
            'away_team': poly_game['away_team'],
            'home_team': poly_game['home_team'],
            'away_code': poly_game['away_code'],
            'home_code': poly_game['home_code'],
            'away_logo': '',
            'home_logo': '',
            'sport': poly_game.get('sport', 'unknown'),
            'polymarket': {
                'away': round(poly_game['away_prob'], 1),
                'home': round(poly_game['home_prob'], 1),
                'raw_away': poly_game.get('away_raw_price', poly_game['away_prob']),
                'raw_home': poly_game.get('home_raw_price', poly_game['home_prob']),
                'url': poly_game.get('url', ''),
                'market_id': poly_game.get('market_id'),
                'away_market_id': poly_game.get('away_market_id'),
                'home_market_id': poly_game.get('home_market_id')
            },
            'kalshi': None,
            'diff': {
                'away': 0,
                'home': 0,
                'max': 0
            },
            'arbitrage_score': 0,
            'game_time': game_time,
            'match_type': 'unmatched',
            'risk_free_arb': None
        }
        
        homepage_games.append(homepage_game)
    
    # Sort homepage games by arbitrage score and max difference
    homepage_games.sort(key=lambda g: (g.get('arbitrage_score', 0), g.get('diff', {}).get('max', 0)), reverse=True)
    
    result = {
        'success': True,
        'timestamp': now.isoformat(),
        'stats': {
            'total_polymarket_games': len(poly_games),
            'total_kalshi_games': len(kalshi_games),
            'matched_games': matched_count,
            'arb_opportunities': len(arb_opportunities),
            'match_rate': (matched_count / min(len(poly_games), len(kalshi_games)) * 100) if min(len(poly_games), len(kalshi_games)) > 0 else 0,
        },
        'matched_games': matched_games,
        'arb_opportunities': arb_opportunities,
        'unmatched_polymarket': [g for g in poly_games if not any(g['away_code'] == m['polymarket']['away_code'] and g['home_code'] == m['polymarket']['home_code'] for m in matched_games)][:50],  # Limit for performance
        'unmatched_kalshi': [g for g in kalshi_games if not any(g['away_code'] == m['kalshi']['away_code'] and g['home_code'] == m['kalshi']['home_code'] for m in matched_games)][:50],
        # Add homepage format for consistency
        'homepage_games': homepage_games
    }
    
    # Cache the result
    try:
        with open('all_sports_cache.json', 'w') as f:
            json.dump(result, f, indent=2)
    except Exception as e:
        print(f"Error caching result: {e}")
    
    return result


def _fuzzy_match(poly_game, kalshi_game, threshold=0.8):
    """
    Fuzzy matching between Polymarket and Kalshi games
    """
    # Exact team code match
    if (poly_game['away_code'] == kalshi_game['away_code'] and 
        poly_game['home_code'] == kalshi_game['home_code']):
        return True
    
    # Fuzzy team name matching
    poly_away = poly_game['away_team'].lower().replace(' ', '').replace('-', '')
    poly_home = poly_game['home_team'].lower().replace(' ', '').replace('-', '')
    kalshi_away = kalshi_game['away_team'].lower().replace(' ', '').replace('-', '')
    kalshi_home = kalshi_game['home_team'].lower().replace(' ', '').replace('-', '')
    
    # Calculate similarity scores
    away_similarity = _calculate_similarity(poly_away, kalshi_away)
    home_similarity = _calculate_similarity(poly_home, kalshi_home)
    
    # Check if both teams match above threshold
    if away_similarity >= threshold and home_similarity >= threshold:
        return True
    
    # Check reversed order (sometimes teams are listed differently)
    if away_similarity >= threshold and _calculate_similarity(poly_away, kalshi_home) >= threshold:
        return True
    if home_similarity >= threshold and _calculate_similarity(poly_home, kalshi_away) >= threshold:
        return True
    
    return False


def _calculate_similarity(str1, str2):
    """
    Calculate string similarity using Levenshtein distance
    """
    if str1 == str2:
        return 1.0
    
    len1, len2 = len(str1), len(str2)
    if len1 == 0:
        return 0.0
    if len2 == 0:
        return 0.0
    
    # Simple similarity based on common characters
    common = sum(1 for c in str1 if c in str2)
    similarity = (2 * common) / (len1 + len2)
    
    return similarity


def _calculate_arb_score(poly_game, kalshi_game):
    """
    Calculate arbitrage opportunity score
    """
    details = _calculate_risk_free_details(poly_game, kalshi_game)
    if not details:
        return 0
    return details['roi_percent']


@app.route('/api/odds')
@app.route('/api/odds/nba')
def get_nba_odds():
    """Get NBA odds comparison data"""
    try:
        data = fetch_nba_data()
        return jsonify(data)
    except Exception as e:
        now = datetime.now()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': now.isoformat()
        }), 500

def _build_nfl_payload(now):
    poly_api = NFLPolymarketAPI()
    kalshi_api = NFLKalshiAPI()

    poly_games = poly_api.get_nfl_games()
    kalshi_games = kalshi_api.get_nfl_games()

    matched = match_games(poly_games, kalshi_games)
    comparisons = calculate_comparisons(matched, NFL_TEAM_LOGOS, nfl_game_history)

    return {
        'success': True,
        'sport': 'nfl',
        'timestamp': now.isoformat(),
        'stats': {
            'total_games': len(comparisons),
            'poly_total': len(poly_games),
            'kalshi_total': len(kalshi_games),
            'matched': len(matched)
        },
        'games': comparisons
    }


def fetch_nfl_data(force_refresh=False):
    now = datetime.now()
    cached = _get_cached_data(nfl_cache, now, force_refresh)
    if cached:
        return cached
    result = _build_nfl_payload(now)
    _set_cache_data(nfl_cache, result, now)
    return result


@app.route('/api/odds/nfl')
def get_nfl_odds():
    """Get NFL odds comparison data"""
    try:
        data = fetch_nfl_data()
        return jsonify(data)
    except Exception as e:
        now = datetime.now()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': now.isoformat()
        }), 500

def _build_nhl_payload(now):
    poly_api = NHLPolymarketAPI()
    kalshi_api = NHLKalshiAPI()

    poly_games = poly_api.get_nhl_games()
    kalshi_games = kalshi_api.get_nhl_games()

    matched = match_games(poly_games, kalshi_games)
    comparisons = calculate_comparisons(matched, NHL_TEAM_LOGOS, nhl_game_history)

    return {
        'success': True,
        'sport': 'nhl',
        'timestamp': now.isoformat(),
        'stats': {
            'total_games': len(comparisons),
            'poly_total': len(poly_games),
            'kalshi_total': len(kalshi_games),
            'matched': len(matched)
        },
        'games': comparisons
    }


def fetch_nhl_data(force_refresh=False):
    now = datetime.now()
    cached = _get_cached_data(nhl_cache, now, force_refresh)
    if cached:
        return cached
    result = _build_nhl_payload(now)
    _set_cache_data(nhl_cache, result, now)
    return result


@app.route('/api/odds/nhl')
def get_nhl_odds():
    """Get NHL odds comparison data"""
    try:
        data = fetch_nhl_data()
        return jsonify(data)
    except Exception as e:
        now = datetime.now()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': now.isoformat()
        }), 500


def _build_football_payload(now):
    poly_api = FootballPolymarketAPI()
    kalshi_api = FootballKalshiAPI()

    poly_games = poly_api.get_football_games()
    kalshi_games = kalshi_api.get_football_games()

    matched = match_games(poly_games, kalshi_games)
    comparisons = calculate_comparisons(matched, FOOTBALL_TEAM_LOGOS, football_game_history)

    return {
        'success': True,
        'sport': 'football',
        'timestamp': now.isoformat(),
        'stats': {
            'total_games': len(comparisons),
            'poly_total': len(poly_games),
            'kalshi_total': len(kalshi_games),
            'matched': len(matched)
        },
        'games': comparisons
    }


def fetch_football_data(force_refresh=False):
    now = datetime.now()
    cached = _get_cached_data(football_cache, now, force_refresh)
    if cached:
        return cached
    result = _build_football_payload(now)
    _set_cache_data(football_cache, result, now)
    return result


@app.route('/api/odds/football')
def get_football_odds():
    """Get Football odds comparison data"""
    try:
        data = fetch_football_data()
        return jsonify(data)
    except Exception as e:
        now = datetime.now()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': now.isoformat()
        }), 500


@app.route('/api/odds/all-sports')
def get_all_sports_odds():
    """Get comprehensive odds data from all sports categories"""
    try:
        data = fetch_all_sports_data()
        return jsonify(data)
    except Exception as e:
        now = datetime.now()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': now.isoformat()
        }), 500


@app.route('/api/odds/all-sports/refresh')
def refresh_all_sports_odds():
    """Force refresh all sports data"""
    try:
        data = fetch_all_sports_data(force_refresh=True)
        return jsonify({
            'success': True,
            'message': 'Data refreshed successfully',
            'data': data
        })
    except Exception as e:
        now = datetime.now()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': now.isoformat()
        }), 500


@app.route('/api/odds/multi')
def get_multi_sport_odds():
    """Aggregate NBA, NFL, NHL, and Football markets into a single feed"""
    now = datetime.now()
    try:
        nba_data = fetch_nba_data()
        nfl_data = fetch_nfl_data()
        nhl_data = fetch_nhl_data()
        football_data = fetch_football_data()

        sport_payloads = {
            'nba': nba_data,
            'nfl': nfl_data,
            'nhl': nhl_data,
            'football': football_data,
        }

        combined_games = []
        overall_stats = {
            'total_games': 0,
            'poly_total': 0,
            'kalshi_total': 0,
            'matched': 0
        }
        per_sport_stats = {}

        for sport, payload in sport_payloads.items():
            stats = payload.get('stats', {})
            per_sport_stats[sport] = stats
            overall_stats['poly_total'] += stats.get('poly_total', 0)
            overall_stats['kalshi_total'] += stats.get('kalshi_total', 0)
            overall_stats['matched'] += stats.get('matched', 0)

            if sport == 'nba':
                game_groups = payload.get('games', {})
                sport_games = (game_groups.get('today') or []) + (game_groups.get('tomorrow') or [])
            else:
                sport_games = payload.get('games', []) or []

            overall_stats['total_games'] += len(sport_games)

            for game in sport_games:
                enriched = dict(game)
                enriched['sport'] = sport.upper()
                combined_games.append(enriched)

        combined_games.sort(key=lambda g: (g.get('arbitrage_score', 0), g.get('diff', {}).get('max', 0)), reverse=True)

        result = {
            'success': True,
            'timestamp': now.isoformat(),
            'sports': list(sport_payloads.keys()),
            'stats': overall_stats,
            'by_sport': per_sport_stats,
            'games': combined_games
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': now.isoformat()
        }), 500


@app.route('/paper-trading')
@app.route('/paper')
def paper_trading_page():
    return send_from_directory('static', 'paper_trading.html')

@app.route('/test-stats')
def test_stats_page():
    return send_from_directory('.', 'test_stats.html')

@app.route('/api/paper/state')
def get_paper_state():
    return jsonify(paper_trader.get_state())

@app.route('/api/paper/reset', methods=['POST'])
def reset_paper_state():
    paper_trader.reset_data()
    return jsonify({'success': True})

def check_paper_trading_settlements():
    print("Checking paper trading settlements...")
    
    poly_api = PolymarketAPI()
    kalshi_api = KalshiAPI()
    
    def resolve_polymarket_winner(market):
        winning_id = market.get('winningOutcomeId')
        if not winning_id:
            return None
            
        token_ids = market.get('clobTokenIds') or market.get('tokenIds')
        if not token_ids:
            tokens = market.get('tokens')
            if tokens and isinstance(tokens, list):
                 for t in tokens:
                     if t.get('tokenId') == winning_id:
                         return t.get('outcome')
            return None
            
        try:
            if winning_id in token_ids:
                index = token_ids.index(winning_id)
                outcomes = json.loads(market.get('outcomes', '[]'))
                if index < len(outcomes):
                    return outcomes[index]
        except:
            pass
            
        return None

    def check_status(platform, market_id):
        if platform == 'Polymarket':
            market = poly_api.get_market(market_id)
            if not market:
                return {'resolved': False}
                
            if market.get('closed') is True:
                 winner_name = resolve_polymarket_winner(market)
                 # Normalize winner name to match leg['team'] or leg['code']?
                 # resolve_polymarket_winner returns the outcome name (e.g. "Boston Celtics").
                 # leg['team'] is "Boston Celtics".
                 return {
                     'resolved': True,
                     'winner': winner_name
                 }
            else:
                 return {'resolved': False}
                 
        elif platform == 'Kalshi':
            market = kalshi_api.get_market(market_id)
            if not market:
                return {'resolved': False}
                
            status = market.get('status')
            if status in ['finalized', 'settled']:
                result = market.get('result')
                if result == 'yes':
                    parts = market_id.split('-')
                    if len(parts) >= 3:
                        # This returns the code, e.g. "BKN"
                        return {'resolved': True, 'winner': parts[2]}
                elif result == 'no':
                     return {'resolved': True, 'winner': 'OTHER_TEAM'}
            else:
                return {'resolved': False}
                
        return {'resolved': False}

    try:
        paper_trader.update_settlements(check_status)
    except Exception as e:
        print(f"Error checking settlements: {e}")

def monitor_job():
    """Background job to check for arbs and execute paper trades"""
    # print(f"[{datetime.now().strftime('%H:%M:%S')}] Running monitor job...")
    
    # Check if paper trading is enabled
    if str(os.environ.get('PAPER_TRADING_ENABLED', 'false')).lower() != 'true':
        return

    try:
        # Use comprehensive all-sports data for maximum coverage
        all_sports_data = fetch_all_sports_data()
        
        if not all_sports_data.get('success'):
            print("Failed to fetch all-sports data, falling back to individual sports")
            # Fallback to individual sports
            nba = fetch_nba_data()
            nfl = fetch_nfl_data()
            nhl = fetch_nhl_data()
            football = fetch_football_data()
            
            all_games = []
            
            # Helper to extract games list
            def extract_games(payload, sport_name):
                if not payload or not payload.get('success'):
                    return []
                games = []
                if sport_name == 'nba':
                    games.extend(payload.get('games', {}).get('today', []))
                    games.extend(payload.get('games', {}).get('tomorrow', []))
                else:
                    games.extend(payload.get('games', []))
                
                # Enriched with sport name
                for g in games:
                    g['sport'] = sport_name.upper()
                return games

            all_games.extend(extract_games(nba, 'nba'))
            all_games.extend(extract_games(nfl, 'nfl'))
            all_games.extend(extract_games(nhl, 'nhl'))
            all_games.extend(extract_games(football, 'football'))
        else:
            # Use the comprehensive data
            all_games = []
            
            # Convert matched games to the expected format for paper trading
            for match in all_sports_data.get('matched_games', []):
                poly = match['polymarket']
                kalshi = match['kalshi']
                
                game = {
                    'away_team': poly['away_team'],
                    'home_team': poly['home_team'],
                    'away_code': poly['away_code'],
                    'home_code': poly['home_code'],
                    'sport': poly.get('sport', 'unknown'),
                    'polymarket': {
                        'away': poly['away_prob'],
                        'home': poly['home_prob'],
                        'raw_away': poly['away_raw_price'],
                        'raw_home': poly['home_raw_price'],
                        'market_id': poly['market_id'],
                        'url': poly['url']
                    },
                    'kalshi': {
                        'away': kalshi['away_prob'],
                        'home': kalshi['home_prob'],
                        'raw_away': kalshi['away_raw_price'],
                        'raw_home': kalshi['home_raw_price'],
                        'away_ticker': kalshi.get('ticker'),
                        'home_ticker': kalshi.get('ticker'),
                        'url': kalshi['url']
                    }
                }
                all_games.append(game)
            
            # Also include unmatched games that might have arbitrage opportunities within the same platform
            for poly_game in all_sports_data.get('unmatched_polymarket', []):
                # Skip games without proper data
                if not all([poly_game.get('away_prob'), poly_game.get('home_prob'), 
                           poly_game.get('away_raw_price'), poly_game.get('home_raw_price')]):
                    continue
                    
                game = {
                    'away_team': poly_game['away_team'],
                    'home_team': poly_game['home_team'],
                    'away_code': poly_game['away_code'],
                    'home_code': poly_game['home_code'],
                    'sport': poly_game.get('sport', 'unknown'),
                    'polymarket': {
                        'away': poly_game['away_prob'],
                        'home': poly_game['home_prob'],
                        'raw_away': poly_game['away_raw_price'],
                        'raw_home': poly_game['home_raw_price'],
                        'market_id': poly_game['market_id'],
                        'url': poly_game['url']
                    },
                    'kalshi': {}  # Empty kalshi data
                }
                all_games.append(game)
        
        print(f"Processing {len(all_games)} games for arbitrage opportunities...")
        
        # 添加调试信息：显示每个体育项目的游戏数量
        sport_counts = {}
        for game in all_games:
            sport = game.get('sport', 'unknown')
            sport_counts[sport] = sport_counts.get(sport, 0) + 1
        print(f"Games by sport: {sport_counts}")
        
        # Check for arbs
        arb_count = 0
        failed_count = 0
        failure_reasons = {}
        
        for game in all_games:
            success, result = paper_trader.execute_arb(game)
            if success:
                arb_count += 1
                trade = result
                print(f"✅ Executed Paper Trade: {trade['game']} (+${trade['profit']:.2f})")
                
                # Send Push Notification
                title = f"💰 New Arb: {trade['game']}"
                content = (
                    f"<b>Sport:</b> {trade['sport']}<br>"
                    f"<b>Type:</b> {trade.get('arb_type', 'unknown')}<br>"
                    f"<b>Profit:</b> ${trade['profit']:.2f}<br>"
                    f"<b>ROI:</b> {trade['roi_percent']:.2f}%<br>"
                    f"<b>Cost:</b> ${trade['cost']:.2f}<br>"
                    f"<b>Time:</b> {trade['timestamp']}"
                )
                notifier.send_push(title, content)
            else:
                failed_count += 1
                reason = result if isinstance(result, str) else "Unknown error"
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
                # 只打印前几个失败的详细信息，避免日志过多
                if failed_count <= 5:
                    game_info = f"{game.get('away_team', '?')} vs {game.get('home_team', '?')} ({game.get('sport', '?')})"
                    print(f"❌ No arb for {game_info}: {reason}")
        
        if arb_count > 0:
            print(f"🎯 Found {arb_count} arbitrage opportunities in this cycle")
        
        if failed_count > 0:
            print(f"📊 Checked {failed_count} games without arbs. Reasons: {failure_reasons}")
                
    except Exception as e:
        print(f"Error in monitor job: {e}")

# Start Scheduler
if not scheduler.running:
    scheduler.add_job(func=monitor_job, trigger="interval", seconds=30)
    scheduler.add_job(func=check_paper_trading_settlements, trigger="interval", minutes=1)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

@app.route('/')
def index():
    """Serve the monitoring dashboard"""
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

if __name__ == '__main__':
    # Create static folder if not exists
    os.makedirs('static', exist_ok=True)

    port = int(os.environ.get('PORT', 5001))
    print("🏀 PolyMix API Server")
    print(f"📊 Starting server at http://localhost:{port}")
    print("🔄 Data refreshes every 30 seconds")
    print("📈 Paper Trading Active")

    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)
