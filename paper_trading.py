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
                    return False, "Market already traded"
            
            POLY_FEE = 0.02
            KALSHI_FEE = 0.07
            SLIPPAGE_ESTIMATE = 0.005
            
            away_platform = risk_detail['bestAwayFrom']
            home_platform = risk_detail['bestHomeFrom']
            
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

        # Calculate effective costs including fees and slippage
        poly_away_eff = poly_away * (1 + POLY_FEE + SLIPPAGE_ESTIMATE)
        kalshi_away_eff = kalshi_away * (1 + KALSHI_FEE + SLIPPAGE_ESTIMATE)
        
        if poly_away_eff < kalshi_away_eff:
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
        else:
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
            
        # Determine best price for Home
        poly_home_eff = poly_home * (1 + POLY_FEE + SLIPPAGE_ESTIMATE)
        kalshi_home_eff = kalshi_home * (1 + KALSHI_FEE + SLIPPAGE_ESTIMATE)
        
        if poly_home_eff < kalshi_home_eff:
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
        else:
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
            
        # Check for valid prices (must be > 0)
        if best_away['price'] <= 0 or best_home['price'] <= 0:
            return False, "Invalid odds (zero price)"

        total_cost_per_unit = best_away['eff'] + best_home['eff']
        
        # Enhanced arbitrage detection - 更宽松的条件以捕获更多机会
        # 1. Perfect arbitrage (cost < 100)
        # 2. Near arbitrage (cost between 100-105, 放宽到105)
        # 3. Partial arbitrage (significant price difference > 3%, 放宽到3%)
        
        is_perfect_arb = total_cost_per_unit < 100
        is_near_arb = 100 <= total_cost_per_unit <= 105  # 从102放宽到105
        is_partial_arb = abs(best_away['price'] - kalshi_away) > 3 or abs(best_home['price'] - kalshi_home) > 3  # 从5%放宽到3%
        
        if not (is_perfect_arb or is_near_arb or is_partial_arb):
            return False, "No profitable arb opportunity"
            
        # Get bet size from env (Target Payout Quantity)
        try:
            target_units = float(os.environ.get('PAPER_TRADING_BET_AMOUNT', 100))
        except:
            target_units = 100.0

        # Dynamic sizing based on arbitrage quality
        if is_perfect_arb:
            units = target_units
            arb_type = "perfect"
        elif is_near_arb:
            units = target_units * 0.5  # Smaller size for near arbs
            arb_type = "near"
        else:
            units = target_units * 0.3  # Even smaller for partial arbs
            arb_type = "partial"

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
            
        # Different ROI thresholds for different arb types - 使用环境变量
        if arb_type == "perfect":
            roi_threshold = max(min_roi, -10.0)  # 允许负ROI
        elif arb_type == "near":
            roi_threshold = max(min_roi, -10.0)  # 允许负ROI
        else:
            roi_threshold = max(min_roi, -10.0)  # 允许负ROI
            
        if roi_percent <= roi_threshold:
            return False, f"ROI ({roi_percent:.2f}%) below threshold ({roi_threshold}%)"

        if total_cost_usd > self.data['balance']:
             return False, "Insufficient balance"
             
        # Check duplicate
        game_id = f"{game['away_code']}@{game['home_code']}"
        for bet in self.data['bets']:
            if bet['id'] == game_id and bet['status'] in ['pending', 'locked']:
                return False, "Market already traded"

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
            'arb_type': arb_type,
            'total_cost_per_unit': total_cost_per_unit,
            'bet_amount_config': target_units
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
