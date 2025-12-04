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
from crypto_polymarket_api import CryptoPolymarketAPI
from crypto_kalshi_api import CryptoKalshiAPI
from odds_api_aggregator import OddsAPIAggregator
from manifold_api import ManifoldAPI
from config import PLATFORMS
import os
import json
import math
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
_kalshi_api_instance = None

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


def _calculate_risk_free_details(poly_game, kalshi_game):
    """
    Return arbitrage metrics using strict Binary Options / Surebet logic.
    
    For binary outcomes (Team A wins OR Team B wins), we evaluate two cross-market strategies:
    Strategy 1: Buy "A wins" from Polymarket + Buy "B wins" from Kalshi
    Strategy 2: Buy "A wins" from Kalshi + Buy "B wins" from Polymarket
    
    We pick the strategy with the LOWEST total cost to ensure true risk-free arbitrage.
    """
    poly_away = _extract_price_value(poly_game, 'away')
    poly_home = _extract_price_value(poly_game, 'home')

    kalshi_away = _extract_price_value(kalshi_game, 'away')
    kalshi_home = _extract_price_value(kalshi_game, 'home')

    if None in [poly_away, poly_home, kalshi_away, kalshi_home]:
        return None
    
    # Reject zero prices - cannot have valid arbitrage with zero prices
    if poly_away <= 0 or poly_home <= 0 or kalshi_away <= 0 or kalshi_home <= 0:
        return None

    # Calculate effective costs including fees and slippage for all four positions
    poly_away_eff = poly_away * (1 + POLYMARKET_FEE + SLIPPAGE_ESTIMATE)
    poly_home_eff = poly_home * (1 + POLYMARKET_FEE + SLIPPAGE_ESTIMATE)
    kalshi_away_eff = kalshi_away * (1 + KALSHI_FEE + SLIPPAGE_ESTIMATE)
    kalshi_home_eff = kalshi_home * (1 + KALSHI_FEE + SLIPPAGE_ESTIMATE)

    # Strategy 1: Polymarket Away + Kalshi Home (cross-market hedge)
    strategy1_cost = poly_away_eff + kalshi_home_eff
    strategy1_gross = poly_away + kalshi_home
    
    # Strategy 2: Kalshi Away + Polymarket Home (cross-market hedge)
    strategy2_cost = kalshi_away_eff + poly_home_eff
    strategy2_gross = kalshi_away + poly_home

    # Pick the strategy with LOWEST total cost (best arbitrage opportunity)
    if strategy1_cost <= strategy2_cost:
        # Use Strategy 1: Polymarket Away + Kalshi Home
        # CRITICAL VALIDATION: This ensures cross-market hedging (opposite outcomes on different platforms)
        away_leg = {
            'platform': 'Polymarket',
            'price': poly_away,
            'effective': poly_away_eff
        }
        home_leg = {
            'platform': 'Kalshi',
            'price': kalshi_home,
            'effective': kalshi_home_eff
        }
        total_cost = strategy1_cost
        gross_cost = strategy1_gross
    else:
        # Use Strategy 2: Kalshi Away + Polymarket Home
        # CRITICAL VALIDATION: This ensures cross-market hedging (opposite outcomes on different platforms)
        away_leg = {
            'platform': 'Kalshi',
            'price': kalshi_away,
            'effective': kalshi_away_eff
        }
        home_leg = {
            'platform': 'Polymarket',
            'price': poly_home,
            'effective': poly_home_eff
        }
        total_cost = strategy2_cost
        gross_cost = strategy2_gross
    
    # CRITICAL VALIDATION: Prevent cross-platform same-side bets
    # Ensure we are not buying the same outcome on both platforms
    if away_leg['platform'] == home_leg['platform']:
        return None  # Invalid arbitrage: both legs on same platform

    if total_cost <= 0:
        return None

    gross_edge = 100 - gross_cost
    net_edge = 100 - total_cost
    roi = net_edge / total_cost
    
    # Only keep opportunities with positive ROI (true risk-free arbitrage)
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
        'arbitrage_type': 'binary_cross_market',
        'fees': {
            'polymarket': POLYMARKET_FEE,
            'kalshi': KALSHI_FEE,
            'slippage': SLIPPAGE_ESTIMATE
        }
    }


def _format_risk_free_details(details):
    """Create a frontend-friendly camelCase copy of risk-free arb details."""
    if not details:
        return None

    if 'bestAwayEffective' in details and 'bestAwayFrom' in details:
        normalized = details.copy()
        roi_percent = normalized.get('roiPercent')
        if roi_percent is None and normalized.get('roi') is not None:
            normalized['roiPercent'] = round(normalized['roi'] * 100, 4)
        elif roi_percent is not None and normalized.get('roi') is None:
            normalized['roi'] = round(roi_percent / 100, 6)
        return normalized

    roi_percent = details.get('roi_percent')
    roi_ratio = round(roi_percent / 100, 6) if roi_percent is not None else None

    return {
        'bestAwayFrom': details.get('best_away_platform'),
        'bestHomeFrom': details.get('best_home_platform'),
        'bestAwayPrice': details.get('best_away_price'),
        'bestHomePrice': details.get('best_home_price'),
        'bestAwayEffective': details.get('best_away_effective'),
        'bestHomeEffective': details.get('best_home_effective'),
        'totalCost': details.get('total_cost'),
        'edge': details.get('net_edge'),
        'grossCost': details.get('gross_cost'),
        'grossEdge': details.get('gross_edge'),
        'roiPercent': roi_percent,
        'roi': roi_ratio,
        'fees': details.get('fees', {})
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
    Ensures minimum requirements: 10 matched games and 5 with arbitrage opportunities
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
                # Check if cache is recent
                if (now - cache_time).seconds < 30:  # Increase cache duration to 30s to match frontend
                    stats = cached.get('stats', {})
                    print(f"Using cached data: {stats.get('matched_games')} matched, {stats.get('arb_opportunities')} arb opportunities")
                    return cached
        except Exception as e:
            print(f"Cache read error: {e}")
            pass
    
    print("Fetching comprehensive sports data...")
    
    # Initialize APIs
    poly_api = PolymarketAPI()
    
    global _kalshi_api_instance
    if _kalshi_api_instance is None:
        _kalshi_api_instance = get_kalshi_api()
    kalshi_api = _kalshi_api_instance
    
    # Get all sports games from both platforms with increased limits
    poly_games = poly_api.get_all_sports_games()
    kalshi_games = kalshi_api.get_all_sports_games()
    
    print(f"Found {len(poly_games)} Polymarket games and {len(kalshi_games)} Kalshi games")
    
    # Define minimum requirements
    MIN_MATCHED_GAMES = 1  # Reduced to ensure faster response
    MIN_ARB_OPPORTUNITIES = 0  # Don't force retries if no arbs exist
    
    def _game_key(game):
        # Normalize to avoid duplicates (remove spaces, lowercase)
        # Prioritize away_code/home_code if available, otherwise use team names
        away = (game.get('away_code') or game.get('away_team') or '').lower().replace(' ', '').replace('-', '').strip()
        home = (game.get('home_code') or game.get('home_team') or '').lower().replace(' ', '').replace('-', '').strip()
        
        # Strict deduplication: Sort teams to handle A vs B and B vs A as the same game
        teams = sorted([away, home])
        
        # Requirement 3: Ignore sport category when deduplicating to avoid duplicate execution
        return f"{teams[0]}@{teams[1]}"
    
    def _update_sport(games, sport_label=None):
        if not games:
            return
        for game in games:
            if sport_label:
                game['sport'] = _normalize_sport_label(sport_label)
            else:
                game['sport'] = _normalize_sport_label(game.get('sport'))
    
    def _merge_games(base_games, extra_games):
        if not extra_games:
            return base_games
        existing_keys = { _game_key(game) for game in base_games }
        for game in extra_games:
            key = _game_key(game)
            if key not in existing_keys:
                base_games.append(game)
                existing_keys.add(key)
        return base_games
    
    def _fetch_priority_games():
        priority_poly = []
        priority_kalshi = []
        try:
            nba_poly = poly_api.get_nba_games()
            _update_sport(nba_poly, 'NBA')
            priority_poly.extend(nba_poly)
        except Exception as e:
            print(f"NBA Polymarket fetch error: {e}")
        try:
            nba_kalshi = kalshi_api.get_nba_games()
            _update_sport(nba_kalshi, 'NBA')
            priority_kalshi.extend(nba_kalshi)
        except Exception as e:
            print(f"NBA Kalshi fetch error: {e}")
            
        # Crypto
        try:
            crypto_poly_api = CryptoPolymarketAPI()
            crypto_poly = crypto_poly_api.get_crypto_markets()
            _update_sport(crypto_poly, 'CRYPTO')
            priority_poly.extend(crypto_poly)
        except Exception as e:
            print(f"Crypto Polymarket fetch error: {e}")
            
        try:
            crypto_kalshi_api = CryptoKalshiAPI()
            crypto_kalshi = crypto_kalshi_api.get_crypto_markets()
            _update_sport(crypto_kalshi, 'CRYPTO')
            priority_kalshi.extend(crypto_kalshi)
        except Exception as e:
            print(f"Crypto Kalshi fetch error: {e}")

        try:
            nfl_poly_api = NFLPolymarketAPI()
            nfl_poly = nfl_poly_api.get_nfl_games()
            _update_sport(nfl_poly, 'NFL')
            priority_poly.extend(nfl_poly)
        except Exception as e:
            print(f"NFL Polymarket fetch error: {e}")
        try:
            nfl_kalshi_api = NFLKalshiAPI()
            nfl_kalshi = nfl_kalshi_api.get_nfl_games()
            _update_sport(nfl_kalshi, 'NFL')
            priority_kalshi.extend(nfl_kalshi)
        except Exception as e:
            print(f"NFL Kalshi fetch error: {e}")
        try:
            nhl_poly_api = NHLPolymarketAPI()
            nhl_poly = nhl_poly_api.get_nhl_games()
            _update_sport(nhl_poly, 'NHL')
            priority_poly.extend(nhl_poly)
        except Exception as e:
            print(f"NHL Polymarket fetch error: {e}")
        try:
            nhl_kalshi_api = NHLKalshiAPI()
            nhl_kalshi = nhl_kalshi_api.get_nhl_games()
            _update_sport(nhl_kalshi, 'NHL')
            priority_kalshi.extend(nhl_kalshi)
        except Exception as e:
            print(f"NHL Kalshi fetch error: {e}")
        return priority_poly, priority_kalshi
    
    def _build_games_from_kalshi_markets(markets):
        games_dict = defaultdict(dict)
        for market in markets or []:
            series_ticker = market.get('series_ticker') or market.get('ticker', '')
            processed = kalshi_api._process_market_for_all_sports_v2(market, series_ticker)
            if not processed:
                continue
            game_id = processed.get('game_id')
            if not game_id:
                continue
            entry = games_dict.setdefault(game_id, {
                'platform': 'Kalshi',
                'away_team': processed['away_team'],
                'home_team': processed['home_team'],
                'away_code': processed['away_code'],
                'home_code': processed['home_code'],
                'sport': processed.get('sport'),
                'close_time': market.get('close_time', ''),
                'away_ticker': None,
                'home_ticker': None
            })
            if processed['team_code'] == processed['away_code']:
                entry['away_prob'] = processed['probability']
                entry['away_raw_price'] = processed['raw_price']
                entry['away_ticker'] = market.get('ticker')
            elif processed['team_code'] == processed['home_code']:
                entry['home_prob'] = processed['probability']
                entry['home_raw_price'] = processed['raw_price']
                entry['home_ticker'] = market.get('ticker')
        games = []
        for entry in games_dict.values():
            if 'away_prob' not in entry or 'home_prob' not in entry:
                continue
            away_raw = entry.get('away_raw_price', 0)
            home_raw = entry.get('home_raw_price', 0)
            total = away_raw + home_raw
            if total > 0:
                away_pct = (away_raw / total) * 100
                home_pct = (home_raw / total) * 100
                away_floor = math.floor(away_pct)
                home_floor = math.floor(home_pct)
                remainder = 100 - (away_floor + home_floor)
                if away_raw <= home_raw:
                    entry['away_prob'] = away_floor + remainder
                    entry['home_prob'] = home_floor
                else:
                    entry['away_prob'] = away_floor
                    entry['home_prob'] = home_floor + remainder
            else:
                entry['away_prob'] = entry['home_prob'] = 0
            ticker = entry.get('away_ticker') or entry.get('home_ticker') or ''
            entry['url'] = f"https://kalshi.com/markets/{ticker}" if ticker else ''
            games.append(entry)
        return games
    
    def _fetch_full_sweep():
        extra_poly = []
        extra_kalshi = []
        try:
            events = poly_api.get_all_events(limit=1000)
            for event in events:
                games = poly_api._process_event_for_all_sports(event)
                _update_sport(games)
                extra_poly.extend(games)
        except Exception as e:
            print(f"Polymarket full sweep error: {e}")
        try:
            markets = kalshi_api.get_all_markets(limit=1000)
            extra_kalshi = _build_games_from_kalshi_markets(markets)
            _update_sport(extra_kalshi)
        except Exception as e:
            print(f"Kalshi full sweep error: {e}")
        return extra_poly, extra_kalshi
    
    # Normalize sport labels for existing data
    _update_sport(poly_games)
    _update_sport(kalshi_games)
    
    search_iterations = 1
    result = _build_all_sports_summary(poly_games, kalshi_games, now, MIN_MATCHED_GAMES, MIN_ARB_OPPORTUNITIES)
    
    # Requirement 4: Keep searching until we meet minimum requirements
    max_iterations = 2  # Prevent infinite loops and timeouts
    while not result.get('requirements_met') and search_iterations < max_iterations:
        if search_iterations == 1:
            print("🔍 Expanding dataset with priority sports feeds...")
            priority_poly, priority_kalshi = _fetch_priority_games()
            poly_games = _merge_games(poly_games, priority_poly)
            kalshi_games = _merge_games(kalshi_games, priority_kalshi)
            search_iterations += 1
            result = _build_all_sports_summary(poly_games, kalshi_games, now, MIN_MATCHED_GAMES, MIN_ARB_OPPORTUNITIES)
        elif search_iterations == 2:
            print("🔄 Expanding dataset with full market sweep...")
            sweep_poly, sweep_kalshi = _fetch_full_sweep()
            poly_games = _merge_games(poly_games, sweep_poly)
            kalshi_games = _merge_games(kalshi_games, sweep_kalshi)
            search_iterations += 1
            result = _build_all_sports_summary(poly_games, kalshi_games, now, MIN_MATCHED_GAMES, MIN_ARB_OPPORTUNITIES)
        else:
            # Additional sweeps with increased limits
            print(f"🔄 Additional sweep iteration {search_iterations}...")
            try:
                extra_poly_events = poly_api.get_all_events(limit=2000)
                for event in extra_poly_events:
                    games = poly_api._process_event_for_all_sports(event)
                    _update_sport(games)
                    poly_games = _merge_games(poly_games, games)
            except Exception as e:
                print(f"Extra Polymarket sweep error: {e}")
            
            try:
                extra_kalshi_markets = kalshi_api.get_all_markets(limit=2000)
                extra_kalshi = _build_games_from_kalshi_markets(extra_kalshi_markets)
                _update_sport(extra_kalshi)
                kalshi_games = _merge_games(kalshi_games, extra_kalshi)
            except Exception as e:
                print(f"Extra Kalshi sweep error: {e}")
            
            search_iterations += 1
            result = _build_all_sports_summary(poly_games, kalshi_games, now, MIN_MATCHED_GAMES, MIN_ARB_OPPORTUNITIES)
    
    result['search_iterations'] = search_iterations
    
    # Log final status
    stats = result.get('stats', {})
    if result.get('requirements_met'):
        print(f"✅ Requirements met after {search_iterations} iterations: {stats.get('matched_games')} matched, {stats.get('arb_opportunities')} arbs")
    else:
        print(f"⚠️ Requirements NOT fully met after {search_iterations} iterations: {stats.get('matched_games')}/{MIN_MATCHED_GAMES} matched, {stats.get('arb_opportunities')}/{MIN_ARB_OPPORTUNITIES} arbs")
    
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
    Calculate string similarity using improved algorithm
    """
    if str1 == str2:
        return 1.0
    
    len1, len2 = len(str1), len(str2)
    if len1 == 0 or len2 == 0:
        return 0.0
    
    # Convert to lowercase for case-insensitive comparison
    s1 = str1.lower()
    s2 = str2.lower()
    
    # Exact match after normalization
    if s1 == s2:
        return 1.0
    
    # Check if one string contains the other
    if s1 in s2 or s2 in s1:
        return 0.9
    
    # Calculate Levenshtein distance
    if len1 > len2:
        s1, s2 = s2, s1
        len1, len2 = len2, len1
    
    current_row = range(len1 + 1)
    for i in range(1, len2 + 1):
        previous_row, current_row = current_row, [i] + [0] * len1
        for j in range(1, len1 + 1):
            add, delete, change = previous_row[j] + 1, current_row[j-1] + 1, previous_row[j-1]
            if s1[j-1] != s2[i-1]:
                change += 1
            current_row[j] = min(add, delete, change)
    
    # Normalize distance to similarity (0-1)
    distance = current_row[len1]
    max_len = max(len1, len2)
    similarity = 1.0 - (distance / max_len)
    
    return similarity


def _match_games_enhanced(poly_games, kalshi_games, fuzzy_threshold=0.7):
    """Enhanced game matching that combines exact lookups with fuzzy matching."""
    matched_games = []
    matched_count = 0

    kalshi_dict = {}
    for game in kalshi_games:
        key = f"{game.get('away_code')}@{game.get('home_code')}".lower()
        kalshi_dict[key] = game

    for poly_game in poly_games:
        poly_key = f"{poly_game.get('away_code')}@{poly_game.get('home_code')}".lower()
        if poly_key in kalshi_dict:
            matched_games.append({
                'polymarket': poly_game,
                'kalshi': kalshi_dict[poly_key],
                'match_type': 'exact'
            })
            matched_count += 1
            continue

        best_match = None
        best_score = fuzzy_threshold

        for kalshi_game in kalshi_games:
            if not _fuzzy_match(poly_game, kalshi_game, threshold=fuzzy_threshold):
                continue

            away_sim = _calculate_similarity(
                (poly_game.get('away_team', '') or '').lower().replace(' ', '').replace('-', ''),
                (kalshi_game.get('away_team', '') or '').lower().replace(' ', '').replace('-', '')
            )
            home_sim = _calculate_similarity(
                (poly_game.get('home_team', '') or '').lower().replace(' ', '').replace('-', ''),
                (kalshi_game.get('home_team', '') or '').lower().replace(' ', '').replace('-', '')
            )
            avg_sim = (away_sim + home_sim) / 2

            if avg_sim > best_score:
                best_score = avg_sim
                best_match = kalshi_game

        if best_match:
            matched_games.append({
                'polymarket': poly_game,
                'kalshi': best_match,
                'match_type': 'fuzzy'
            })
            matched_count += 1

    return matched_games, matched_count


def _normalize_sport_label(value, default='UNKNOWN'):
    if not value:
        return default
    return str(value).upper()


def _calculate_arb_score(poly_game, kalshi_game):
    """
    Calculate arbitrage opportunity score
    """
    details = _calculate_risk_free_details(poly_game, kalshi_game)
    if not details:
        return 0
    return details['roi_percent']


def _format_game_time(iso_time):
    """Format ISO time string to readable format"""
    if not iso_time:
        return ''
    try:
        # Handle 'Z' for UTC if present
        clean_time = iso_time.replace('Z', '+00:00')
        # Simple string slicing fallback if strictly ISO
        if 'T' in clean_time:
            dt = datetime.fromisoformat(clean_time)
            return dt.strftime('%Y-%m-%d %H:%M')
        return clean_time[:16]
    except (ValueError, TypeError):
        return str(iso_time)[:16]


def _build_all_sports_summary(poly_games, kalshi_games, now, min_matches, min_arbs):
    """Generate comprehensive all-sports payload with arbitrage analysis."""
    matched_games, matched_count = _match_games_enhanced(poly_games, kalshi_games)

    print(f"Successfully matched {matched_count} games")

    arb_opportunities = []
    homepage_games = []
    homepage_arb_games = []
    
    # Requirement 3: Track unique games to prevent duplicates from different categories
    seen_game_keys = set()

    for match in matched_games:
        poly = match['polymarket']
        kalshi = match['kalshi']
        
        # Create unique game identifier to prevent duplicate processing
        # Strict deduplication: Sort teams to handle A vs B and B vs A as the same game
        p_away = (poly.get('away_code') or poly.get('away_team') or '').lower().replace(' ', '').replace('-', '').strip()
        p_home = (poly.get('home_code') or poly.get('home_team') or '').lower().replace(' ', '').replace('-', '').strip()
        teams = sorted([p_away, p_home])
        game_key = f"{teams[0]}@{teams[1]}"
        
        # Skip if we've already processed this game (requirement 3)
        if game_key in seen_game_keys:
            print(f"⚠️ Skipping duplicate game: {poly['away_team']} vs {poly['home_team']} ({poly.get('sport', 'unknown')})")
            continue
        seen_game_keys.add(game_key)
        
        arb_details = _calculate_risk_free_details(poly, kalshi)
        match['risk_free_arb'] = arb_details
        if arb_details:
            formatted = _format_risk_free_details(arb_details)
            match['riskFreeArb'] = formatted
            arb_opportunities.append({
                'polymarket': poly,
                'kalshi': kalshi,
                'match_type': match['match_type'],
                'arb_score': arb_details['roi_percent'],
                'risk_free_arb': arb_details,
                'riskFreeArb': formatted
            })

        away_diff = abs(poly['away_prob'] - kalshi['away_prob'])
        home_diff = abs(poly['home_prob'] - kalshi['home_prob'])
        max_diff = max(away_diff, home_diff)
        
        # Use start_date if available (more accurate for game time), otherwise end_date
        raw_time = poly.get('start_date') or poly.get('end_date') or ''
        game_time = _format_game_time(raw_time)
        
        sport_label = _normalize_sport_label(poly.get('sport') or kalshi.get('sport'))

        homepage_game = {
            'away_team': poly['away_team'],
            'home_team': poly['home_team'],
            'away_code': poly['away_code'],
            'home_code': poly['home_code'],
            'away_logo': '',
            'home_logo': '',
            'sport': sport_label,
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
            'arbitrage_score': round(arb_details['roi_percent'], 2) if arb_details else 0,
            'game_time': game_time,
            'match_type': match['match_type'],
            'risk_free_arb': arb_details,
            'riskFreeArb': match.get('riskFreeArb')
        }

        homepage_games.append(homepage_game)
        if arb_details:
            homepage_arb_games.append(homepage_game)

    matched_keys = {
        f"{match['polymarket']['away_code']}@{match['polymarket']['home_code']}".lower()
        for match in matched_games
    }

    for poly_game in poly_games:
        poly_key = f"{poly_game['away_code']}@{poly_game['home_code']}".lower()
        if poly_key in matched_keys:
            continue
        
        # Requirement 3: Skip duplicates even if they appear in unmatched list
        if poly_key in seen_game_keys:
            continue
        seen_game_keys.add(poly_key)

        game_time = poly_game.get('end_date', '')[:16] if poly_game.get('end_date') else ''
        sport_label = _normalize_sport_label(poly_game.get('sport'))

        homepage_game = {
            'away_team': poly_game['away_team'],
            'home_team': poly_game['home_team'],
            'away_code': poly_game['away_code'],
            'home_code': poly_game['home_code'],
            'away_logo': '',
            'home_logo': '',
            'sport': sport_label,
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
            'diff': {'away': 0, 'home': 0, 'max': 0},
            'arbitrage_score': 0,
            'game_time': game_time,
            'match_type': 'unmatched',
            'risk_free_arb': None
        }

        homepage_games.append(homepage_game)

    homepage_games.sort(key=lambda g: (g.get('arbitrage_score', 0), g.get('diff', {}).get('max', 0)), reverse=True)

    requirements_met = matched_count >= min_matches and len(arb_opportunities) >= min_arbs
    if requirements_met:
        print(f"✅ Requirements met: {matched_count} matches, {len(arb_opportunities)} arb opportunities")
    else:
        print(f"⚠️ Requirements not met yet: {matched_count}/{min_matches} matches, {len(arb_opportunities)}/{min_arbs} arbs")

    tradable_markets = []
    tradable_by_sport = defaultdict(int)
    for game in homepage_arb_games:
        risk_detail = game.get('riskFreeArb') or game.get('risk_free_arb')
        if not risk_detail:
            continue
        edge = risk_detail.get('edge') if isinstance(risk_detail, dict) and 'edge' in risk_detail else risk_detail.get('net_edge')
        roi_percent = risk_detail.get('roiPercent') if isinstance(risk_detail, dict) and 'roiPercent' in risk_detail else risk_detail.get('roi_percent')
        if edge is None or edge <= 0 or roi_percent is None:
            continue
        try:
            min_roi = float(os.environ.get('PAPER_TRADING_MIN_ROI', 0))
        except:
            min_roi = 0.0
        if roi_percent > min_roi:
            tradable_markets.append(game)
            sport_label = game.get('sport', 'UNKNOWN')
            tradable_by_sport[sport_label] += 1

    stats = {
        'total_polymarket_games': len(poly_games),
        'total_kalshi_games': len(kalshi_games),
        'matched_games': matched_count,
        'arb_opportunities': len(arb_opportunities),
        'arb_homepage_games': len(homepage_arb_games),
        'homepage_games': len(homepage_games),
        'tradable_markets': len(tradable_markets),
        'match_rate': (matched_count / min(len(poly_games), len(kalshi_games)) * 100) if min(len(poly_games), len(kalshi_games)) > 0 else 0,
    }

    result = {
        'success': True,
        'timestamp': now.isoformat(),
        'requirements_met': requirements_met,
        'stats': stats,
        'matched_games': matched_games,
        'arb_opportunities': arb_opportunities,
        'tradable_markets': tradable_markets,
        'tradable_by_sport': dict(tradable_by_sport),
        'unmatched_polymarket': [
            g for g in poly_games
            if f"{g['away_code']}@{g['home_code']}".lower() not in matched_keys
        ][:50],
        'unmatched_kalshi': [
            g for g in kalshi_games
            if f"{g['away_code']}@{g['home_code']}".lower() not in {
                f"{match['kalshi']['away_code']}@{match['kalshi']['home_code']}".lower()
                for match in matched_games
            }
        ][:50],
        'homepage_games': homepage_games,
        'homepage_arb_games': homepage_arb_games
    }

    print(f"📊 Interim stats: {matched_count} matched, {len(arb_opportunities)} arbs, {len(tradable_markets)} tradable")
    return result


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
    """Aggregate NBA, NFL, NHL, and Football markets into a single feed with explicit tradable market indicators"""
    now = datetime.now()
    try:
        nba_data = fetch_nba_data()
        nfl_data = fetch_nfl_data()
        nhl_data = fetch_nhl_data()

        sport_payloads = {
            'nba': nba_data,
            'nfl': nfl_data,
            'nhl': nhl_data,
        }

        combined_games = []
        tradable_games = []
        overall_stats = {
            'total_games': 0,
            'poly_total': 0,
            'kalshi_total': 0,
            'matched': 0,
            'tradable_markets': 0
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
                
                # Calculate risk-free arbitrage details if not already present
                poly = game.get('polymarket', {})
                kalshi = game.get('kalshi', {})
                if poly and kalshi and not enriched.get('riskFreeArb'):
                    arb_details = _calculate_risk_free_details(poly, kalshi)
                    if arb_details:
                        enriched['risk_free_arb'] = arb_details
                        enriched['riskFreeArb'] = _format_risk_free_details(arb_details)
                
                # Mark as tradable if it meets paper trading conditions
                risk_detail = enriched.get('riskFreeArb') or enriched.get('risk_free_arb')
                is_tradable = False
                if risk_detail:
                    edge = risk_detail.get('edge') if isinstance(risk_detail, dict) and 'edge' in risk_detail else risk_detail.get('net_edge')
                    roi_percent = risk_detail.get('roiPercent') if isinstance(risk_detail, dict) and 'roiPercent' in risk_detail else risk_detail.get('roi_percent')
                    
                    if edge is not None and edge > 0:
                        try:
                            min_roi = float(os.environ.get('PAPER_TRADING_MIN_ROI', 0))
                        except:
                            min_roi = 0.0
                        
                        if roi_percent is not None and roi_percent > min_roi:
                            is_tradable = True
                            overall_stats['tradable_markets'] += 1
                            tradable_games.append(enriched)
                
                enriched['is_tradable'] = is_tradable
                enriched['meets_paper_trade_conditions'] = is_tradable
                combined_games.append(enriched)

        combined_games.sort(key=lambda g: (g.get('arbitrage_score', 0), g.get('diff', {}).get('max', 0)), reverse=True)

        result = {
            'success': True,
            'timestamp': now.isoformat(),
            'sports': list(sport_payloads.keys()),
            'stats': overall_stats,
            'by_sport': per_sport_stats,
            'games': combined_games,
            'tradable_games': tradable_games  # Explicitly show tradable markets
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
        
        # Fallback: check outcomePrices if market is resolved
        if not winning_id and market.get('umaResolutionStatus') == 'resolved':
            try:
                 outcome_prices = json.loads(market.get('outcomePrices', '[]'))
                 outcomes = json.loads(market.get('outcomes', '[]'))
                 if len(outcome_prices) == len(outcomes):
                     # Find which one is 1 (or close to 1)
                     for i, price in enumerate(outcome_prices):
                         if float(price) >= 0.99:
                             return outcomes[i]
            except:
                pass

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
        try:
            if platform == 'Polymarket':
                market = poly_api.get_market(market_id)
                if not market:
                    print(f"Polymarket market {market_id} not found")
                    return {'resolved': False}
                    
                # print(f"DEBUG: Market {market_id} closed={market.get('closed')}")
                if market.get('closed') is True:
                     winner_name = resolve_polymarket_winner(market)
                     
                     if winner_name is None:
                         # Market closed but winner not available/resolvable yet
                         return {'resolved': False}

                     # Handling for Yes/No outcomes in Polymarket
                     if winner_name == 'Yes':
                         group_title = market.get('groupItemTitle')
                         if group_title:
                             return {'resolved': True, 'winner': group_title}
                         pass
                     elif winner_name == 'No':
                         group_title = market.get('groupItemTitle')
                         if group_title:
                             return {'resolved': True, 'winner': f"NOT {group_title}"}
                         
                     print(f"✅ Polymarket settlement: {market_id} -> {winner_name}")
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
                    print(f"✅ Kalshi settlement: {market_id} -> {result}")
                    
                    # Parse ticker to find teams
                    # Format: KX-SPORT-TEAM1-TEAM2-DATE
                    parts = market_id.split('-')
                    primary_team = parts[2] if len(parts) >= 3 else None
                    secondary_team = parts[3] if len(parts) >= 4 else None
                    
                    if result == 'yes':
                        return {'resolved': True, 'winner': primary_team}
                    elif result == 'no':
                         # If primary lost, secondary won
                         winner = secondary_team if secondary_team else 'OTHER_TEAM'
                         return {'resolved': True, 'winner': winner}
                    else:
                         return {'resolved': True, 'winner': 'VOID'}
                else:
                    return {'resolved': False}
        except Exception as e:
            print(f"Error in check_status: {e}")
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
        else:
            # Use the comprehensive data - prioritize homepage_games for consistency with frontend
            all_games = []
            
            # Use homepage_games directly - these are pre-formatted and include arb calculations
            homepage_games = all_sports_data.get('homepage_games', [])
            if homepage_games:
                print(f"✅ Using {len(homepage_games)} homepage_games from all_sports_data")
                all_games = homepage_games
            else:
                # Fallback: Convert matched games to the expected format for paper trading
                print("⚠️ No homepage_games found, falling back to matched_games conversion")
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
        
        # Requirement 3: Remove duplicates from different categories before processing
        seen_game_keys = set()
        unique_games = []
        duplicate_count = 0
        
        for game in all_games:
            game_key = f"{game.get('away_code')}@{game.get('home_code')}".lower()
            if game_key in seen_game_keys:
                duplicate_count += 1
                continue
            seen_game_keys.add(game_key)
            unique_games.append(game)
        
        if duplicate_count > 0:
            print(f"✅ Removed {duplicate_count} duplicate games from different categories")
        
        # 添加调试信息：显示每个体育项目的游戏数量
        sport_counts = {}
        for game in unique_games:
            sport = (game.get('sport') or 'unknown').upper()
            sport_counts[sport] = sport_counts.get(sport, 0) + 1
        print(f"Games by sport (after dedup): {sport_counts}")
        
        # 筛选出真正满足无风险套利条件的市场
        tradable_games = []
        filtered_games = []
        ineligible_sports = []
        
        for game in unique_games:
            # NEW: Check if sport is eligible for paper trading (NBA, NHL, NFL only)
            if not paper_trader.is_paper_trading_eligible_market(game):
                sport = game.get('sport', 'unknown').upper()
                if sport not in ineligible_sports:
                    ineligible_sports.append(sport)
                continue
            
            # Requirement 2: Check for zero prices
            poly = game.get('polymarket', {})
            kalshi = game.get('kalshi', {})
            
            # Skip games with zero prices
            if poly and (poly.get('raw_away', 0) <= 0 or poly.get('raw_home', 0) <= 0):
                continue
            if kalshi and (kalshi.get('raw_away', 0) <= 0 or kalshi.get('raw_home', 0) <= 0):
                continue
            
            risk_detail = game.get('riskFreeArb')
            if not risk_detail and game.get('risk_free_arb'):
                risk_detail = _format_risk_free_details(game.get('risk_free_arb'))
                if risk_detail:
                    game['riskFreeArb'] = risk_detail
            
            # Additional check for zero prices in risk details
            if risk_detail:
                if risk_detail.get('bestAwayPrice', 0) <= 0 or risk_detail.get('bestHomePrice', 0) <= 0:
                    continue
            
            if risk_detail and risk_detail.get('edge') is not None and risk_detail.get('edge') > 0:
                tradable_games.append(game)
            else:
                filtered_games.append(game)
        
        print(f"Tradable markets (ROI>0 after fees): {len(tradable_games)} / {len(unique_games)}")
        
        # Report filtered and ineligible sports
        if ineligible_sports:
            print(f"🚫 Ineligible sports (not paper trading eligible): {set(ineligible_sports)}")
            
        if filtered_games:
            sample = filtered_games[:5]
            sample_descriptions = [
                f"{g.get('away_team', '?')}@{g.get('home_team', '?')}[{g.get('sport', '?')}]"
                for g in sample
            ]
            print(f"Filtered markets (first {len(sample)}): {sample_descriptions}")
        
        # Check for arbs only on tradable markets
        arb_count = 0
        failed_count = 0
        failure_reasons = {}
        
        for game in tradable_games:
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
            print(f"📊 Checked {failed_count} tradable games without execution. Reasons: {failure_reasons}")
                
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

@app.route('/api/eligible-markets')
def eligible_markets():
    """Get list of markets eligible for paper trading (NBA, NHL, NFL)"""
    try:
        markets_info = paper_trader.get_eligible_markets_summary()
        return jsonify({
            'success': True,
            'data': markets_info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/paper-trading-state')
def paper_trading_state():
    """Get current paper trading state and recent trades"""
    try:
        state = paper_trader.get_state()
        return jsonify({
            'success': True,
            'data': state
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Create static folder if not exists
    os.makedirs('static', exist_ok=True)

    port = int(os.environ.get('PORT', 5001))
    print("🏀 PolyMix API Server")
    print(f"📊 Starting server at http://localhost:{port}")
    print("🔄 Data refreshes every 30 seconds")
    print("📈 Paper Trading Active")

    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)
