# NBA Team Name Mapping between Polymarket and Kalshi
# Polymarket uses team nicknames, Kalshi uses city names

# NBA Team Logos (using ESPN's CDN)
TEAM_LOGOS = {
    'ATL': 'https://a.espncdn.com/i/teamlogos/nba/500/atl.png',
    'BOS': 'https://a.espncdn.com/i/teamlogos/nba/500/bos.png',
    'BKN': 'https://a.espncdn.com/i/teamlogos/nba/500/bkn.png',
    'CHA': 'https://a.espncdn.com/i/teamlogos/nba/500/cha.png',
    'CHI': 'https://a.espncdn.com/i/teamlogos/nba/500/chi.png',
    'CLE': 'https://a.espncdn.com/i/teamlogos/nba/500/cle.png',
    'DAL': 'https://a.espncdn.com/i/teamlogos/nba/500/dal.png',
    'DEN': 'https://a.espncdn.com/i/teamlogos/nba/500/den.png',
    'DET': 'https://a.espncdn.com/i/teamlogos/nba/500/det.png',
    'GSW': 'https://a.espncdn.com/i/teamlogos/nba/500/gs.png',
    'HOU': 'https://a.espncdn.com/i/teamlogos/nba/500/hou.png',
    'IND': 'https://a.espncdn.com/i/teamlogos/nba/500/ind.png',
    'LAC': 'https://a.espncdn.com/i/teamlogos/nba/500/lac.png',
    'LAL': 'https://a.espncdn.com/i/teamlogos/nba/500/lal.png',
    'MEM': 'https://a.espncdn.com/i/teamlogos/nba/500/mem.png',
    'MIA': 'https://a.espncdn.com/i/teamlogos/nba/500/mia.png',
    'MIL': 'https://a.espncdn.com/i/teamlogos/nba/500/mil.png',
    'MIN': 'https://a.espncdn.com/i/teamlogos/nba/500/min.png',
    'NOP': 'https://a.espncdn.com/i/teamlogos/nba/500/no.png',
    'NYK': 'https://a.espncdn.com/i/teamlogos/nba/500/ny.png',
    'OKC': 'https://a.espncdn.com/i/teamlogos/nba/500/okc.png',
    'ORL': 'https://a.espncdn.com/i/teamlogos/nba/500/orl.png',
    'PHI': 'https://a.espncdn.com/i/teamlogos/nba/500/phi.png',
    'PHX': 'https://a.espncdn.com/i/teamlogos/nba/500/phx.png',
    'POR': 'https://a.espncdn.com/i/teamlogos/nba/500/por.png',
    'SAC': 'https://a.espncdn.com/i/teamlogos/nba/500/sac.png',
    'SAS': 'https://a.espncdn.com/i/teamlogos/nba/500/sa.png',
    'TOR': 'https://a.espncdn.com/i/teamlogos/nba/500/tor.png',
    'UTA': 'https://a.espncdn.com/i/teamlogos/nba/500/utah.png',
    'WAS': 'https://a.espncdn.com/i/teamlogos/nba/500/wsh.png',
}

# Complete NBA team mapping
NBA_TEAMS = {
    # Team Code: (Polymarket Name, Kalshi Name, Full Name)
    'ATL': ('Hawks', 'Atlanta', 'Atlanta Hawks'),
    'BOS': ('Celtics', 'Boston', 'Boston Celtics'),
    'BKN': ('Nets', 'Brooklyn', 'Brooklyn Nets'),
    'CHA': ('Hornets', 'Charlotte', 'Charlotte Hornets'),
    'CHI': ('Bulls', 'Chicago', 'Chicago Bulls'),
    'CLE': ('Cavaliers', 'Cleveland', 'Cleveland Cavaliers'),
    'DAL': ('Mavericks', 'Dallas', 'Dallas Mavericks'),
    'DEN': ('Nuggets', 'Denver', 'Denver Nuggets'),
    'DET': ('Pistons', 'Detroit', 'Detroit Pistons'),
    'GSW': ('Warriors', 'Golden State', 'Golden State Warriors'),
    'HOU': ('Rockets', 'Houston', 'Houston Rockets'),
    'IND': ('Pacers', 'Indiana', 'Indiana Pacers'),
    'LAC': ('Clippers', 'Los Angeles C', 'Los Angeles Clippers'),
    'LAL': ('Lakers', 'Los Angeles L', 'Los Angeles Lakers'),
    'MEM': ('Grizzlies', 'Memphis', 'Memphis Grizzlies'),
    'MIA': ('Heat', 'Miami', 'Miami Heat'),
    'MIL': ('Bucks', 'Milwaukee', 'Milwaukee Bucks'),
    'MIN': ('Timberwolves', 'Minnesota', 'Minnesota Timberwolves'),
    'NOP': ('Pelicans', 'New Orleans', 'New Orleans Pelicans'),
    'NYK': ('Knicks', 'New York K', 'New York Knicks'),
    'OKC': ('Thunder', 'Oklahoma City', 'Oklahoma City Thunder'),
    'ORL': ('Magic', 'Orlando', 'Orlando Magic'),
    'PHI': ('76ers', 'Philadelphia', 'Philadelphia 76ers'),
    'PHX': ('Suns', 'Phoenix', 'Phoenix Suns'),
    'POR': ('Trail Blazers', 'Portland', 'Portland Trail Blazers'),
    'SAC': ('Kings', 'Sacramento', 'Sacramento Kings'),
    'SAS': ('Spurs', 'San Antonio', 'San Antonio Spurs'),
    'TOR': ('Raptors', 'Toronto', 'Toronto Raptors'),
    'UTA': ('Jazz', 'Utah', 'Utah Jazz'),
    'WAS': ('Wizards', 'Washington', 'Washington Wizards'),
}

# Create reverse mappings for easy lookup
POLYMARKET_TO_CODE = {v[0]: k for k, v in NBA_TEAMS.items()}
KALSHI_TO_CODE = {v[1]: k for k, v in NBA_TEAMS.items()}
FULLNAME_TO_CODE = {v[2]: k for k, v in NBA_TEAMS.items()}

def normalize_team_name(name, platform='polymarket'):
    """
    Normalize team name to standard team code

    Args:
        name: Team name string
        platform: 'polymarket', 'kalshi', 'odds_api', 'manifold'

    Returns:
        Team code (e.g., 'GSW', 'LAL') or None if not found
    """
    name = name.strip()

    if platform == 'polymarket':
        return POLYMARKET_TO_CODE.get(name)
    elif platform == 'kalshi':
        return KALSHI_TO_CODE.get(name)
    elif platform in ['odds_api', 'manifold']:
        # These platforms use full team names
        return FULLNAME_TO_CODE.get(name)
    else:
        # Try all mappings
        return (POLYMARKET_TO_CODE.get(name) or
                KALSHI_TO_CODE.get(name) or
                FULLNAME_TO_CODE.get(name))

def get_team_info(code):
    """Get team information by team code"""
    return NBA_TEAMS.get(code)
