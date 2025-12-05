#!/usr/bin/env python3
"""
Configuration file for PolyMix
Add your API keys here
"""

import os

# =======================
# API Keys
# =======================
API_KEYS = {
    'ODDS_API_KEY': os.environ.get('ODDS_API_KEY', ''),   # Odds API key
    'PROP_ODDS_KEY': os.environ.get('PROP_ODDS_KEY', ''), # Props odds key
}

# =======================
# Platform Settings
# =======================
PLATFORMS = {
    'polymarket': {
        'enabled': True,
        'name': 'Polymarket',
        'color': '#6366f1',  # Indigo
        'requires_key': False,
    },
    'kalshi': {
        'enabled': True,
        'name': 'Kalshi',
        'color': '#10b981',  # Green
        'requires_key': False,
    },
    'odds_api': {
        'enabled': True,  # Enable when you add API key
        'name': 'Sportsbooks',
        'color': '#f59e0b',  # Amber
        'requires_key': True,
        'description': 'Aggregated odds from DraftKings, FanDuel, BetMGM, etc.',
    },
    'manifold': {
        'enabled': True,  # Enable if you want community predictions
        'name': 'Manifold',
        'color': '#8b5cf6',  # Purple
        'requires_key': False,
        'description': 'Community prediction market',
    },
}

# =======================
# Platform fee settings
# 用于“真实手续费 + 只显示净套利”的计算
# 所有费率用小数表示，例如 0.02 = 2%
# =======================
PLATFORM_FEES = {
    'polymarket': {
        # Trading fee rate on filled orders (approximate).
        # 请改成你真实的 Polymarket 手续费
        'trading_fee_rate': 0.02,
    },
    'kalshi': {
        # Trading fee rate on filled orders (approximate).
        # 请改成你真实的 Kalshi 手续费
        'trading_fee_rate': 0.07,
    },
    'manifold': {
        # Manifold 一般可认为交易费 ~0（如果有特殊费率就改这里）
        'trading_fee_rate': 0.00,
    },
    'odds_api': {
        # 普通菠菜商只用来对比赔率，一般不在这里直接交易 → 设 0 即可
        'trading_fee_rate': 0.00,
    },
}

# =======================
# Cache settings
# =======================
CACHE_DURATION = 30  # seconds

# =======================
# Display settings
# =======================
MAX_GAMES_DISPLAYED = 100
SHOW_INACTIVE_PLATFORMS = True
