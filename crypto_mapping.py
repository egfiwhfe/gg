"""
Crypto currency logos and display mapping
"""

CRYPTO_LOGOS = {
    'BTC': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png',
    'ETH': 'https://cryptologos.cc/logos/ethereum-eth-logo.png',
    'SOL': 'https://cryptologos.cc/logos/solana-sol-logo.png',
    'ADA': 'https://cryptologos.cc/logos/cardano-ada-logo.png',
    'DOGE': 'https://cryptologos.cc/logos/dogecoin-doge-logo.png',
    'XRP': 'https://cryptologos.cc/logos/xrp-xrp-logo.png',
    'DOT': 'https://cryptologos.cc/logos/polkadot-new-dot-logo.png',
    'AVAX': 'https://cryptologos.cc/logos/avalanche-avax-logo.png',
    'MATIC': 'https://cryptologos.cc/logos/polygon-matic-logo.png',
    'LINK': 'https://cryptologos.cc/logos/chainlink-link-logo.png',
}

CRYPTO_DISPLAY_NAMES = {
    'BTC': 'Bitcoin',
    'ETH': 'Ethereum',
    'SOL': 'Solana',
    'ADA': 'Cardano',
    'DOGE': 'Dogecoin',
    'XRP': 'Ripple',
    'DOT': 'Polkadot',
    'AVAX': 'Avalanche',
    'MATIC': 'Polygon',
    'LINK': 'Chainlink',
}

def get_crypto_logo(code: str) -> str:
    """Get logo URL for a crypto currency code"""
    return CRYPTO_LOGOS.get(code.upper(), '')

def get_crypto_display_name(code: str) -> str:
    """Get display name for a crypto currency code"""
    return CRYPTO_DISPLAY_NAMES.get(code.upper(), code.upper())
