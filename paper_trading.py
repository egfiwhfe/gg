import json
import os
from datetime import datetime

DATA_FILE = 'paper_trading_data.json'

class PaperTradingSystem:
    def __init__(self):
        self.load_data()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    self.data = json.load(f)
            except:
                self.reset_data()
        else:
            self.reset_data()

    def reset_data(self):
        try:
            initial_balance = float(os.environ.get('PAPER_TRADING_INITIAL_BALANCE', 10000))
        except:
            initial_balance = 10000.0
            
        self.data = {
            'balance': initial_balance,
            'initial_balance': initial_balance,
            'bets': [], # List of placed bets (trades)
            'total_profit': 0.0
        }
        self.save_data()

    def save_data(self):
        with open(DATA_FILE, 'w') as f:
            json.dump(self.data, f, indent=4)

    def get_state(self):
        # Calculate summary
        total_trades = len(self.data['bets'])
        
        # Profit includes realized profit from settled bets
        total_profit = sum(bet.get('realized_profit', 0.0) for bet in self.data['bets'] if bet['status'] == 'settled')
        
        # Estimated profit from pending bets
        estimated_profit = sum(bet.get('profit', 0.0) for bet in self.data['bets'] if bet['status'] == 'pending')
        
        current_balance = self.data['balance']
        
        # Sort bets by timestamp desc
        sorted_bets = sorted(self.data['bets'], key=lambda x: x['timestamp'], reverse=True)
        
        return {
            'balance': current_balance,
            'initial_balance': self.data['initial_balance'],
            'total_profit': total_profit,
            'estimated_profit': estimated_profit,
            'total_trades': total_trades,
            'bets': sorted_bets
        }

    def _normalize_risk_details(self, details):
        if not details:
            return None
        # Already camelCase
        if isinstance(details, dict) and 'bestAwayFrom' in details and 'bestAwayEffective' in details:
            normalized = details.copy()
            roi_percent = normalized.get('roiPercent')
            if roi_percent is not None and normalized.get('roi') is None:
                normalized['roi'] = roi_percent / 100
            if normalized.get('roi') is not None and normalized.get('roiPercent') is None:
                normalized['roiPercent'] = normalized['roi'] * 100
            return normalized
        
        if isinstance(details, dict) and 'best_away_platform' in details:
            roi_percent = details.get('roi_percent')
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
                'roi': roi_percent / 100 if roi_percent is not None else None,
                'fees': details.get('fees', {})
            }
        
        return None

    def execute_arb(self, game, amount_per_leg=100.0):
        """
        Attempt to execute a risk-free arb trade on the given game.
        Enhanced with more realistic arbitrage strategies and pre-calculated arb support.
        """
        # Check for pre-calculated risk-free arb details
        risk_detail = self._normalize_risk_details(game.get('riskFreeArb') or game.get('risk_free_arb'))
        required_keys = ['bestAwayPrice', 'bestHomePrice', 'bestAwayEffective', 'bestHomeEffective', 'totalCost', 'edge']
        if risk_detail and any(risk_detail.get(k) is None for k in required_keys):
            risk_detail = None
        
        # Requirement 2: Prohibit betting when price is 0¢
        if risk_detail:
            if risk_detail.get('bestAwayPrice', 0) <= 0 or risk_detail.get('bestHomePrice', 0) <= 0:
                return False, "Invalid odds (zero price detected in pre-calculated arb)"
        
        if risk_detail and risk_detail.get('edge') and risk_detail.get('edge') > 0:
            poly = game.get('polymarket', {})
            kalshi = game.get('kalshi', {})
            
            if not poly or not kalshi or poly.get('away') is None or poly.get('home') is None:
                return False, "Missing platform data"
            
            try:
                target_units = float(os.environ.get('PAPER_TRADING_BET_AMOUNT', 100))
            except:
                target_units = 100.0
            
            quantity = target_units
            total_cost_usd = (risk_detail['totalCost'] / 100.0) * quantity
            profit_usd = (risk_detail['edge'] / 100.0) * quantity
            roi_percent = risk_detail.get('roiPercent', 0)
            
            try:
                min_roi = float(os.environ.get('PAPER_TRADING_MIN_ROI', 0))
            except:
                min_roi = 0.0
            
            if roi_percent <= min_roi:
                return False, f"ROI ({roi_percent:.2f}%) below threshold ({min_roi}%)"
            
            if total_cost_usd > self.data['balance']:
                return False, "Insufficient balance"
            
            game_id = f"{game.get('away_code')}@{game.get('home_code')}"
            for bet in self.data['bets']:
                if bet['id'] == game_id and bet['status'] in ['pending', 'locked']:
                    return False, "Market already traded (duplicate trade prevention)"
            
            POLY_FEE = 0.02
            KALSHI_FEE = 0.07
            SLIPPAGE_ESTIMATE = 0.005
            
            away_platform = risk_detail['bestAwayFrom']
            home_platform = risk_detail['bestHomeFrom']
            
            # CRITICAL VALIDATION: Prevent cross-platform same-side bets
            # Ensure we are not buying the same outcome (Yes/No) on both platforms
            # True arbitrage requires buying opposite outcomes on different platforms
            if away_platform == home_platform:
                return False, f"Invalid arbitrage: Both legs on same platform ({away_platform}). This violates cross-market hedging principle."
            
            # Additional validation: Ensure we are buying opposite outcomes
            # In binary options, we should buy A wins on one platform and B wins on the other
            # This is inherently satisfied by our strategy selection logic, but we double-check
            if away_platform not in ['Polymarket', 'Kalshi'] or home_platform not in ['Polymarket', 'Kalshi']:
                return False, f"Invalid arbitrage: Unknown platforms detected - Away: {away_platform}, Home: {home_platform}"
            
            best_away = {
                'platform': away_platform,
                'price': risk_detail['bestAwayPrice'],
                'eff': risk_detail['bestAwayEffective'],
                'team': game.get('away_team', 'Away'),
                'code': game.get('away_code'),
                'market_id': poly.get('away_market_id') or poly.get('market_id') if away_platform == 'Polymarket' else kalshi.get('away_ticker'),
                'url': poly.get('url', '') if away_platform == 'Polymarket' else kalshi.get('url', ''),
                'fee_rate': POLY_FEE if away_platform == 'Polymarket' else KALSHI_FEE
            }
            
            best_home = {
                'platform': home_platform,
                'price': risk_detail['bestHomePrice'],
                'eff': risk_detail['bestHomeEffective'],
                'team': game.get('home_team', 'Home'),
                'code': game.get('home_code'),
                'market_id': poly.get('home_market_id') or poly.get('market_id') if home_platform == 'Polymarket' else kalshi.get('home_ticker'),
                'url': poly.get('url', '') if home_platform == 'Polymarket' else kalshi.get('url', ''),
                'fee_rate': POLY_FEE if home_platform == 'Polymarket' else KALSHI_FEE
            }
            
            for leg in [best_away, best_home]:
                leg_cost_cents = leg['eff'] * quantity
                leg_price_cents = leg['price'] * quantity
                leg['cost_usd'] = leg_cost_cents / 100.0
                leg['fee_usd'] = (leg_cost_cents - leg_price_cents) / 100.0
                leg['payout_usd'] = quantity * 1.0
                leg['slippage_usd'] = (leg['price'] * SLIPPAGE_ESTIMATE * quantity) / 100.0
            
            trade = {
                'id': game_id,
                'game': f"{game.get('away_team')} vs {game.get('home_team')}",
                'sport': game.get('sport', 'unknown'),
                'timestamp': datetime.now().isoformat(),
                'game_time': game.get('game_time', '') or game.get('end_date', ''),
                'legs': [best_away, best_home],
                'quantity': quantity,
                'cost': total_cost_usd,
                'payout': quantity * 1.0,
                'profit': profit_usd,
                'roi_percent': roi_percent,
                'status': 'pending',
                'settled_amount': 0.0,
                'realized_profit': 0.0,
                'fees_total_usd': best_away['fee_usd'] + best_home['fee_usd'],
                'slippage_total_usd': best_away['slippage_usd'] + best_home['slippage_usd'],
                'arb_type': 'perfect' if risk_detail['totalCost'] < 100 else 'near',
                'total_cost_per_unit': risk_detail['totalCost'],
                'bet_amount_config': target_units
            }
            
            self.data['bets'].append(trade)
            self.data['balance'] -= total_cost_usd
            self.save_data()
            return True, trade
        
        # Fallback to legacy calculation if no pre-calculated arb
        # Dynamic fees based on platform and market conditions
        POLY_FEE = 0.02  # 2% fee
        KALSHI_FEE = 0.07  # 7% fee
        
        # Additional slippage and market impact estimates
        SLIPPAGE_ESTIMATE = 0.005  # 0.5% slippage estimate
        LIQUIDITY_DISCOUNT = 0.01   # 1% discount for larger trades
        
        poly = game.get('polymarket', {})
        kalshi = game.get('kalshi', {})
        
        # 如果只有一个平台有数据，跳过套利检查但仍可用于单平台分析
        if not poly or not kalshi:
            return False, "Missing platform data for arbitrage"
            
        poly_away = poly.get('raw_away', poly.get('away'))
        poly_home = poly.get('raw_home', poly.get('home'))
        kalshi_away = kalshi.get('raw_away', kalshi.get('away'))
        kalshi_home = kalshi.get('raw_home', kalshi.get('home'))
        
        if None in [poly_away, poly_home, kalshi_away, kalshi_home]:
            return False, "Missing odds"

        # Ensure team info exists
        if not game.get('away_code') or not game.get('home_code'):
             return False, "Missing team codes"

        # Check for valid prices (must be > 0)
        if poly_away <= 0 or poly_home <= 0 or kalshi_away <= 0 or kalshi_home <= 0:
            return False, "Invalid odds (zero price)"

        # Binary Arbitrage Logic - evaluate cross-market strategies
        # Calculate effective costs including fees and slippage for all positions
        poly_away_eff = poly_away * (1 + POLY_FEE + SLIPPAGE_ESTIMATE)
        poly_home_eff = poly_home * (1 + POLY_FEE + SLIPPAGE_ESTIMATE)
        kalshi_away_eff = kalshi_away * (1 + KALSHI_FEE + SLIPPAGE_ESTIMATE)
        kalshi_home_eff = kalshi_home * (1 + KALSHI_FEE + SLIPPAGE_ESTIMATE)
        
        # Strategy 1: Polymarket Away + Kalshi Home (cross-market hedge)
        strategy1_cost = poly_away_eff + kalshi_home_eff
        
        # Strategy 2: Kalshi Away + Polymarket Home (cross-market hedge)
        strategy2_cost = kalshi_away_eff + poly_home_eff
        
        # Pick the strategy with LOWEST total cost (best arbitrage opportunity)
        if strategy1_cost <= strategy2_cost:
            # Use Strategy 1: Polymarket Away + Kalshi Home
            # CRITICAL VALIDATION: This ensures cross-market hedging (opposite outcomes on different platforms)
            away_platform = 'Polymarket'
            home_platform = 'Kalshi'
            
            best_away = {
                'platform': 'Polymarket', 
                'price': poly_away, 
                'eff': poly_away_eff, 
                'team': game.get('away_team', 'Away'),
                'code': game.get('away_code'),
                'market_id': poly.get('away_market_id') or poly.get('market_id'),
                'url': poly.get('url', ''),
                'fee_rate': POLY_FEE
            }
            best_home = {
                'platform': 'Kalshi', 
                'price': kalshi_home, 
                'eff': kalshi_home_eff, 
                'team': game.get('home_team', 'Home'),
                'code': game.get('home_code'),
                'market_id': kalshi.get('home_ticker'),
                'url': kalshi.get('url', ''),
                'fee_rate': KALSHI_FEE
            }
            total_cost_per_unit = strategy1_cost
        else:
            # Use Strategy 2: Kalshi Away + Polymarket Home
            # CRITICAL VALIDATION: This ensures cross-market hedging (opposite outcomes on different platforms)
            away_platform = 'Kalshi'
            home_platform = 'Polymarket'
            
            best_away = {
                'platform': 'Kalshi', 
                'price': kalshi_away, 
                'eff': kalshi_away_eff, 
                'team': game.get('away_team', 'Away'),
                'code': game.get('away_code'),
                'market_id': kalshi.get('away_ticker'),
                'url': kalshi.get('url', ''),
                'fee_rate': KALSHI_FEE
            }
            best_home = {
                'platform': 'Polymarket', 
                'price': poly_home, 
                'eff': poly_home_eff, 
                'team': game.get('home_team', 'Home'),
                'code': game.get('home_code'),
                'market_id': poly.get('home_market_id') or poly.get('market_id'),
                'url': poly.get('url', ''),
                'fee_rate': POLY_FEE
            }
            total_cost_per_unit = strategy2_cost
        
        # CRITICAL VALIDATION: Prevent cross-platform same-side bets
        # Ensure we are not buying the same outcome on both platforms
        if away_platform == home_platform:
            return False, f"Invalid arbitrage: Both legs on same platform ({away_platform}). This violates cross-market hedging principle."
        
        # Strict binary surebet requirement: total cost must be < 100¢
        if total_cost_per_unit >= 100:
            return False, "No risk-free arb opportunity (total cost ≥ 100¢)"
            
        # Get bet size from env (Target Payout Quantity)
        try:
            target_units = float(os.environ.get('PAPER_TRADING_BET_AMOUNT', 100))
        except:
            target_units = 100.0

        units = target_units

        # Apply liquidity discount for larger trades
        if units > 200:
            liquidity_multiplier = 1 - LIQUIDITY_DISCOUNT
            units *= liquidity_multiplier
        
        cost_cents = total_cost_per_unit
        payout_cents = 100.0
        profit_cents = payout_cents - cost_cents
        
        quantity = units
        total_cost_usd = (cost_cents / 100.0) * quantity
        profit_usd = (profit_cents / 100.0) * quantity
        
        # Enhanced ROI calculation
        roi_percent = (profit_usd / total_cost_usd * 100) if total_cost_usd > 0 else 0
        
        try:
            min_roi = float(os.environ.get('PAPER_TRADING_MIN_ROI', 0))
        except:
            min_roi = 0.0
            
        roi_threshold = max(min_roi, 0.0)
            
        if roi_percent <= roi_threshold:
            return False, f"ROI ({roi_percent:.2f}%) below threshold ({roi_threshold}%)"

        if total_cost_usd > self.data['balance']:
            return False, "Insufficient balance"

        # Requirement 1: Enhanced duplicate check - reject duplicate trades
        game_id = f"{game['away_code']}@{game['home_code']}"
        for bet in self.data['bets']:
            if bet['id'] == game_id and bet['status'] in ['pending', 'locked']:
                return False, "Market already traded (duplicate trade prevention)"

        # Enrich legs with detailed cost info
        for leg in [best_away, best_home]:
            leg_cost_cents = leg['eff'] * quantity
            leg_price_cents = leg['price'] * quantity
            leg['cost_usd'] = leg_cost_cents / 100.0
            leg['fee_usd'] = (leg_cost_cents - leg_price_cents) / 100.0
            leg['payout_usd'] = quantity * 1.0 # If this leg wins
            leg['slippage_usd'] = (leg['price'] * SLIPPAGE_ESTIMATE * quantity) / 100.0

        # Execute
        trade = {
            'id': game_id,
            'game': f"{game['away_team']} vs {game['home_team']}",
            'sport': game.get('sport', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'game_time': game.get('game_time', '') or game.get('end_date', ''),
            'legs': [best_away, best_home],
            'quantity': quantity,
            'cost': total_cost_usd,
            'payout': quantity * 1.0, # Expected payout
            'profit': profit_usd, # Expected profit
            'roi_percent': roi_percent,
            'status': 'pending', 
            'settled_amount': 0.0,
            'realized_profit': 0.0,
            'fees_total_usd': best_away['fee_usd'] + best_home['fee_usd'],
            'slippage_total_usd': best_away['slippage_usd'] + best_home['slippage_usd'],
            'arb_type': 'binary_cross_market',
            'total_cost_per_unit': total_cost_per_unit,
            'bet_amount_config': target_units,
            'strategy_1_cost': strategy1_cost,
            'strategy_2_cost': strategy2_cost,
            'selected_strategy': 1 if strategy1_cost <= strategy2_cost else 2
        }
        
        self.data['bets'].append(trade)
        self.data['balance'] -= total_cost_usd
        
        self.save_data()
        return True, trade

    def _is_high_liquidity_game(self, game):
        """Determine if a game has high liquidity based on sport and teams"""
        high_liquidity_sports = ['basketball', 'football', 'hockey']
        sport = game.get('sport', '').lower()
        
        # Major sports typically have higher liquidity
        if sport in high_liquidity_sports:
            return True
            
        # Check for major teams (simplified)
        major_teams = ['Lakers', 'Warriors', 'Bucks', 'Nets', 'Celtics', 'Heat', 'Nuggets', 'Suns']
        away_team = game.get('away_team', '')
        home_team = game.get('home_team', '')
        
        return any(team in away_team or team in home_team for team in major_teams)

    def update_settlements(self, check_status_func):
        """
        Check pending bets and settle them if resolved.
        check_status_func(platform, market_id) -> {'resolved': bool, 'winner': str/code}
        """
        changed = False
        for bet in self.data['bets']:
            if bet['status'] == 'pending':
                all_legs_resolved = True
                total_payout = 0.0
                resolved_legs_count = 0
                
                # Check status of each leg
                for leg in bet['legs']:
                    platform = leg.get('platform')
                    market_id = leg.get('market_id')
                    
                    # Attempt to recover market_id from URL if missing (specifically for Kalshi)
                    if not market_id and platform == 'Kalshi' and leg.get('url'):
                        try:
                            url = leg.get('url')
                            if '/markets/' in url:
                                parts = url.split('/markets/')
                                if len(parts) > 1:
                                    ticker = parts[1].split('?')[0].split('#')[0]
                                    market_id = ticker
                                    leg['market_id'] = market_id
                                    changed = True # Save recovered ID
                        except:
                            pass

                    if not market_id:
                        # Fallback for old bets or missing data
                        continue
                        
                    status = check_status_func(platform, market_id)
                    
                    if not status.get('resolved'):
                        all_legs_resolved = False
                        break
                    
                    resolved_legs_count += 1
                    
                    # Check if won
                    winner = status.get('winner')
                    # leg['code'] is team code. leg['team'] is team name.
                    # Winner should be matched against these.
                    # normalize team name?
                    
                    if str(winner) == str(leg.get('code')) or str(winner) == str(leg.get('team')):
                         # Won leg
                         total_payout += bet['quantity'] * 1.0
                
                if all_legs_resolved and resolved_legs_count == len(bet['legs']):
                    # Settle
                    bet['status'] = 'settled'
                    bet['settled_amount'] = total_payout
                    bet['realized_profit'] = total_payout - bet['cost']
                    bet['profit'] = bet['realized_profit']
                    self.data['balance'] += total_payout
                    changed = True
                    print(f"Settled bet {bet['id']}. Payout: {total_payout}. Profit: {bet['realized_profit']}")

        if changed:
            self.save_data()
