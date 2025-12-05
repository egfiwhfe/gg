"""NHL Team Name Mapping between Polymarket and Kalshi"""

# NHL Team Logos
NHL_TEAM_LOGOS = {
    'ANA': 'https://a.espncdn.com/i/teamlogos/nhl/500/ana.png',
    'ARI': 'https://a.espncdn.com/i/teamlogos/nhl/500/ari.png',
    'BOS': 'https://a.espncdn.com/i/teamlogos/nhl/500/bos.png',
    'BUF': 'https://a.espncdn.com/i/teamlogos/nhl/500/buf.png',
    'CGY': 'https://a.espncdn.com/i/teamlogos/nhl/500/cgy.png',
    'CAR': 'https://a.espncdn.com/i/teamlogos/nhl/500/car.png',
    'CHI': 'https://a.espncdn.com/i/teamlogos/nhl/500/chi.png',
    'COL': 'https://a.espncdn.com/i/teamlogos/nhl/500/col.png',
    'CBJ': 'https://a.espncdn.com/i/teamlogos/nhl/500/cbj.png',
    'DAL': 'https://a.espncdn.com/i/teamlogos/nhl/500/dal.png',
    'DET': 'https://a.espncdn.com/i/teamlogos/nhl/500/det.png',
    'EDM': 'https://a.espncdn.com/i/teamlogos/nhl/500/edm.png',
    'FLA': 'https://a.espncdn.com/i/teamlogos/nhl/500/fla.png',
    'LAK': 'https://a.espncdn.com/i/teamlogos/nhl/500/la.png',
    'MIN': 'https://a.espncdn.com/i/teamlogos/nhl/500/min.png',
    'MTL': 'https://a.espncdn.com/i/teamlogos/nhl/500/mtl.png',
    'NSH': 'https://a.espncdn.com/i/teamlogos/nhl/500/nsh.png',
    'NJD': 'https://a.espncdn.com/i/teamlogos/nhl/500/nj.png',
    'NYI': 'https://a.espncdn.com/i/teamlogos/nhl/500/nyi.png',
    'NYR': 'https://a.espncdn.com/i/teamlogos/nhl/500/nyr.png',
    'OTT': 'https://a.espncdn.com/i/teamlogos/nhl/500/ott.png',
    'PHI': 'https://a.espncdn.com/i/teamlogos/nhl/500/phi.png',
    'PIT': 'https://a.espncdn.com/i/teamlogos/nhl/500/pit.png',
    'SJS': 'https://a.espncdn.com/i/teamlogos/nhl/500/sj.png',
    'SEA': 'https://a.espncdn.com/i/teamlogos/nhl/500/sea.png',
    'STL': 'https://a.espncdn.com/i/teamlogos/nhl/500/stl.png',
    'TBL': 'https://a.espncdn.com/i/teamlogos/nhl/500/tb.png',
    'TOR': 'https://a.espncdn.com/i/teamlogos/nhl/500/tor.png',
    'UTA': 'https://a.espncdn.com/i/teamlogos/nhl/500/uta.png',
    'VAN': 'https://a.espncdn.com/i/teamlogos/nhl/500/van.png',
    'VGK': 'https://a.espncdn.com/i/teamlogos/nhl/500/vgk.png',
    'WSH': 'https://a.espncdn.com/i/teamlogos/nhl/500/wsh.png',
    'WPG': 'https://a.espncdn.com/i/teamlogos/nhl/500/wpg.png',
}

# Complete NHL team mapping
NHL_TEAMS = {
    'ANA': ('Ducks', 'Anaheim', 'Anaheim Ducks'),
    'ARI': ('Coyotes', 'Arizona', 'Arizona Coyotes'),
    'BOS': ('Bruins', 'Boston', 'Boston Bruins'),
    'BUF': ('Sabres', 'Buffalo', 'Buffalo Sabres'),
    'CGY': ('Flames', 'Calgary', 'Calgary Flames'),
    'CAR': ('Hurricanes', 'Carolina', 'Carolina Hurricanes'),
    'CHI': ('Blackhawks', 'Chicago', 'Chicago Blackhawks'),
    'COL': ('Avalanche', 'Colorado', 'Colorado Avalanche'),
    'CBJ': ('Blue Jackets', 'Columbus', 'Columbus Blue Jackets'),
    'DAL': ('Stars', 'Dallas', 'Dallas Stars'),
    'DET': ('Red Wings', 'Detroit', 'Detroit Red Wings'),
    'EDM': ('Oilers', 'Edmonton', 'Edmonton Oilers'),
    'FLA': ('Panthers', 'Florida', 'Florida Panthers'),
    'LAK': ('Kings', 'Los Angeles', 'Los Angeles Kings'),
    'MIN': ('Wild', 'Minnesota', 'Minnesota Wild'),
    'MTL': ('Canadiens', 'Montreal', 'Montreal Canadiens'),
    'NSH': ('Predators', 'Nashville', 'Nashville Predators'),
    'NJD': ('Devils', 'New Jersey', 'New Jersey Devils'),
    'NYI': ('Islanders', 'New York I', 'New York Islanders'),
    'NYR': ('Rangers', 'New York R', 'New York Rangers'),
    'OTT': ('Senators', 'Ottawa', 'Ottawa Senators'),
    'PHI': ('Flyers', 'Philadelphia', 'Philadelphia Flyers'),
    'PIT': ('Penguins', 'Pittsburgh', 'Pittsburgh Penguins'),
    'SJS': ('Sharks', 'San Jose', 'San Jose Sharks'),
    'SEA': ('Kraken', 'Seattle', 'Seattle Kraken'),
    'STL': ('Blues', 'St. Louis', 'St. Louis Blues'),
    'TBL': ('Lightning', 'Tampa Bay', 'Tampa Bay Lightning'),
    'TOR': ('Maple Leafs', 'Toronto', 'Toronto Maple Leafs'),
    'UTA': ('Utah', 'Utah', 'Utah Hockey Club'),
    'VAN': ('Canucks', 'Vancouver', 'Vancouver Canucks'),
    'VGK': ('Golden Knights', 'Vegas', 'Vegas Golden Knights'),
    'WSH': ('Capitals', 'Washington', 'Washington Capitals'),
    'WPG': ('Jets', 'Winnipeg', 'Winnipeg Jets'),
}

POLYMARKET_TO_CODE = {v[0]: k for k, v in NHL_TEAMS.items()}
KALSHI_TO_CODE = {v[1]: k for k, v in NHL_TEAMS.items()}
FULLNAME_TO_CODE = {v[2]: k for k, v in NHL_TEAMS.items()}

# Utah team has multiple names
POLYMARKET_TO_CODE['Hockey Club'] = 'UTA'
POLYMARKET_TO_CODE['Utah Hockey Club'] = 'UTA'
KALSHI_TO_CODE['Utah'] = 'UTA'
KALSHI_TO_CODE['Utah HC'] = 'UTA'

# Add self-mappings for Kalshi codes
for code in NHL_TEAMS.keys():
    KALSHI_TO_CODE[code] = code



def normalize_team_name(name, platform='polymarket'):
    """Normalize team name to standard code"""
    name = name.strip()
    
    if platform == 'polymarket':
        return POLYMARKET_TO_CODE.get(name)
    elif platform == 'kalshi':
        return KALSHI_TO_CODE.get(name)
    elif platform in ['odds_api', 'manifold']:
        return FULLNAME_TO_CODE.get(name)
    else:
        return (POLYMARKET_TO_CODE.get(name) or
                KALSHI_TO_CODE.get(name) or
                FULLNAME_TO_CODE.get(name))


def get_team_info(code):
    """Get team info by code"""
    return NHL_TEAMS.get(code)
