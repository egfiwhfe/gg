# NFL Team Name Mapping between Polymarket and Kalshi
# Polymarket uses team nicknames, Kalshi uses city names

# NFL Team Logos (using ESPN's CDN)
NFL_TEAM_LOGOS = {
    'ARI': 'https://a.espncdn.com/i/teamlogos/nfl/500/ari.png',
    'ATL': 'https://a.espncdn.com/i/teamlogos/nfl/500/atl.png',
    'BAL': 'https://a.espncdn.com/i/teamlogos/nfl/500/bal.png',
    'BUF': 'https://a.espncdn.com/i/teamlogos/nfl/500/buf.png',
    'CAR': 'https://a.espncdn.com/i/teamlogos/nfl/500/car.png',
    'CHI': 'https://a.espncdn.com/i/teamlogos/nfl/500/chi.png',
    'CIN': 'https://a.espncdn.com/i/teamlogos/nfl/500/cin.png',
    'CLE': 'https://a.espncdn.com/i/teamlogos/nfl/500/cle.png',
    'DAL': 'https://a.espncdn.com/i/teamlogos/nfl/500/dal.png',
    'DEN': 'https://a.espncdn.com/i/teamlogos/nfl/500/den.png',
    'DET': 'https://a.espncdn.com/i/teamlogos/nfl/500/det.png',
    'GB': 'https://a.espncdn.com/i/teamlogos/nfl/500/gb.png',
    'HOU': 'https://a.espncdn.com/i/teamlogos/nfl/500/hou.png',
    'IND': 'https://a.espncdn.com/i/teamlogos/nfl/500/ind.png',
    'JAX': 'https://a.espncdn.com/i/teamlogos/nfl/500/jax.png',
    'KC': 'https://a.espncdn.com/i/teamlogos/nfl/500/kc.png',
    'LAC': 'https://a.espncdn.com/i/teamlogos/nfl/500/lac.png',
    'LAR': 'https://a.espncdn.com/i/teamlogos/nfl/500/lar.png',
    'LV': 'https://a.espncdn.com/i/teamlogos/nfl/500/lv.png',
    'MIA': 'https://a.espncdn.com/i/teamlogos/nfl/500/mia.png',
    'MIN': 'https://a.espncdn.com/i/teamlogos/nfl/500/min.png',
    'NE': 'https://a.espncdn.com/i/teamlogos/nfl/500/ne.png',
    'NO': 'https://a.espncdn.com/i/teamlogos/nfl/500/no.png',
    'NYG': 'https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png',
    'NYJ': 'https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png',
    'PHI': 'https://a.espncdn.com/i/teamlogos/nfl/500/phi.png',
    'PIT': 'https://a.espncdn.com/i/teamlogos/nfl/500/pit.png',
    'SF': 'https://a.espncdn.com/i/teamlogos/nfl/500/sf.png',
    'SEA': 'https://a.espncdn.com/i/teamlogos/nfl/500/sea.png',
    'TB': 'https://a.espncdn.com/i/teamlogos/nfl/500/tb.png',
    'TEN': 'https://a.espncdn.com/i/teamlogos/nfl/500/ten.png',
    'WAS': 'https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png',
}

# Complete NFL team mapping
# Team Code: (Polymarket Name, Kalshi Name, Full Name)
NFL_TEAMS = {
    'ARI': ('Cardinals', 'Arizona', 'Arizona Cardinals'),
    'ATL': ('Falcons', 'Atlanta', 'Atlanta Falcons'),
    'BAL': ('Ravens', 'Baltimore', 'Baltimore Ravens'),
    'BUF': ('Bills', 'Buffalo', 'Buffalo Bills'),
    'CAR': ('Panthers', 'Carolina', 'Carolina Panthers'),
    'CHI': ('Bears', 'Chicago', 'Chicago Bears'),
    'CIN': ('Bengals', 'Cincinnati', 'Cincinnati Bengals'),
    'CLE': ('Browns', 'Cleveland', 'Cleveland Browns'),
    'DAL': ('Cowboys', 'Dallas', 'Dallas Cowboys'),
    'DEN': ('Broncos', 'Denver', 'Denver Broncos'),
    'DET': ('Lions', 'Detroit', 'Detroit Lions'),
    'GB': ('Packers', 'Green Bay', 'Green Bay Packers'),
    'HOU': ('Texans', 'Houston', 'Houston Texans'),
    'IND': ('Colts', 'Indianapolis', 'Indianapolis Colts'),
    'JAX': ('Jaguars', 'Jacksonville', 'Jacksonville Jaguars'),
    'KC': ('Chiefs', 'Kansas City', 'Kansas City Chiefs'),
    'LAC': ('Chargers', 'Los Angeles C', 'Los Angeles Chargers'),
    'LAR': ('Rams', 'Los Angeles R', 'Los Angeles Rams'),
    'LV': ('Raiders', 'Las Vegas', 'Las Vegas Raiders'),
    'MIA': ('Dolphins', 'Miami', 'Miami Dolphins'),
    'MIN': ('Vikings', 'Minnesota', 'Minnesota Vikings'),
    'NE': ('Patriots', 'New England', 'New England Patriots'),
    'NO': ('Saints', 'New Orleans', 'New Orleans Saints'),
    'NYG': ('Giants', 'New York G', 'New York Giants'),
    'NYJ': ('Jets', 'New York J', 'New York Jets'),
    'PHI': ('Eagles', 'Philadelphia', 'Philadelphia Eagles'),
    'PIT': ('Steelers', 'Pittsburgh', 'Pittsburgh Steelers'),
    'SF': ('49ers', 'San Francisco', 'San Francisco 49ers'),
    'SEA': ('Seahawks', 'Seattle', 'Seattle Seahawks'),
    'TB': ('Buccaneers', 'Tampa Bay', 'Tampa Bay Buccaneers'),
    'TEN': ('Titans', 'Tennessee', 'Tennessee Titans'),
    'WAS': ('Commanders', 'Washington', 'Washington Commanders'),
}

# Create reverse mappings for easy lookup
POLYMARKET_TO_CODE = {v[0]: k for k, v in NFL_TEAMS.items()}
KALSHI_TO_CODE = {v[1]: k for k, v in NFL_TEAMS.items()}

def normalize_team_name(name, platform='polymarket'):
    """
    Normalize team name to standard team code

    Args:
        name: Team name string
        platform: 'polymarket' or 'kalshi'

    Returns:
        Team code (e.g., 'KC', 'GB') or None if not found
    """
    name = name.strip()

    if platform == 'polymarket':
        return POLYMARKET_TO_CODE.get(name)
    elif platform == 'kalshi':
        return KALSHI_TO_CODE.get(name)
    else:
        # Try both
        return POLYMARKET_TO_CODE.get(name) or KALSHI_TO_CODE.get(name)

def get_team_info(code):
    """Get team information by team code"""
    return NFL_TEAMS.get(code)
