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
    'LTC': 'https://cryptologos.cc/logos/litecoin-ltc-logo.png',
    'NEAR': 'https://cryptologos.cc/logos/near-protocol-near-logo.png',
    'ATOM': 'https://cryptologos.cc/logos/cosmos-atom-logo.png',
    'ARB': 'https://cryptologos.cc/logos/arbitrum-arb-logo.png',
    'OP': 'https://cryptologos.cc/logos/optimism-op-logo.png',
    'SUI': 'https://cryptologos.cc/logos/sui-sui-logo.png',
    'APT': 'https://cryptologos.cc/logos/aptos-apt-logo.png',
    'INJ': 'https://cryptologos.cc/logos/injective-inj-logo.png',
    'FIL': 'https://cryptologos.cc/logos/filecoin-fil-logo.png',
    'ICP': 'https://cryptologos.cc/logos/internet-computer-icp-logo.png',
    'SEI': 'https://cryptologos.cc/logos/sei-sei-logo.png',
    'PEPE': 'https://cryptologos.cc/logos/pepe-pepe-logo.png',
    'SHIB': 'https://cryptologos.cc/logos/shiba-inu-shib-logo.png',
    'BLUR': 'https://cryptologos.cc/logos/blur-blur-logo.png',
    'LIDO': 'https://cryptologos.cc/logos/lido-dao-ldo-logo.png',
    'UNI': 'https://cryptologos.cc/logos/uniswap-uni-logo.png',
    'AAVE': 'https://cryptologos.cc/logos/aave-aave-logo.png',
    'CRV': 'https://cryptologos.cc/logos/curve-crv-logo.png',
    'MKR': 'https://cryptologos.cc/logos/maker-mkr-logo.png',
    'COMP': 'https://cryptologos.cc/logos/compound-comp-logo.png',
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
    'LTC': 'Litecoin',
    'NEAR': 'Near Protocol',
    'ATOM': 'Cosmos',
    'ARB': 'Arbitrum',
    'OP': 'Optimism',
    'SUI': 'Sui',
    'APT': 'Aptos',
    'INJ': 'Injective',
    'FIL': 'Filecoin',
    'ICP': 'Internet Computer',
    'SEI': 'Sei',
    'PEPE': 'Pepe',
    'SHIB': 'Shiba Inu',
    'BLUR': 'Blur',
    'LIDO': 'Lido DAO',
    'UNI': 'Uniswap',
    'AAVE': 'Aave',
    'CRV': 'Curve',
    'MKR': 'Maker',
    'COMP': 'Compound',
}

def get_crypto_logo(code: str) -> str:
    """Get logo URL for a crypto currency code"""
    return CRYPTO_LOGOS.get(code.upper(), '')

def get_crypto_display_name(code: str) -> str:
    """Get display name for a crypto currency code"""
    return CRYPTO_DISPLAY_NAMES.get(code.upper(), code.upper())
