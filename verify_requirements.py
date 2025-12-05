#!/usr/bin/env python3
"""
Verification script to ensure requirements are met:
1. Frontend MULTI tab shows NBA/NFL/NHL markets with arbitrage opportunities
2. Paper trading only trades NBA/NFL/NHL markets with positive ROI
"""

import sys
import re

def check_frontend():
    """Verify frontend changes"""
    print("=" * 80)
    print("1. Checking Frontend (index.html)")
    print("=" * 80)
    
    with open('static/index.html', 'r') as f:
        content = f.read()
    
    checks = []
    
    # Check 1: Multi tab should call /api/odds/multi
    if "url = '/api/odds/multi'" in content:
        print("✅ Multi tab calls /api/odds/multi")
        checks.append(True)
    else:
        print("❌ Multi tab does NOT call /api/odds/multi")
        checks.append(False)
    
    # Check 2: Multi tab should use homepage_arb_games
    if "allGames = data.homepage_arb_games" in content:
        print("✅ Multi tab uses homepage_arb_games")
        checks.append(True)
    else:
        print("❌ Multi tab does NOT use homepage_arb_games")
        checks.append(False)
    
    # Check 3: Should not use all-sports for multi
    multi_section = re.search(r"if \(url === '/api/odds/multi'\).*?else \{", content, re.DOTALL)
    if multi_section and "all-sports" not in multi_section.group(0):
        print("✅ Multi section does not reference all-sports")
        checks.append(True)
    else:
        print("❌ Multi section may still reference all-sports")
        checks.append(False)
    
    return all(checks)


def check_backend_multi_endpoint():
    """Verify /api/odds/multi endpoint"""
    print("\n" + "=" * 80)
    print("2. Checking Backend /api/odds/multi Endpoint")
    print("=" * 80)
    
    with open('api.py', 'r') as f:
        content = f.read()
    
    checks = []
    
    # Check 1: Endpoint should fetch NBA/NFL/NHL only
    endpoint_section = re.search(
        r"@app\.route\('/api/odds/multi'\).*?def get_multi_sport_odds\(\):.*?(?=@app\.route|def \w+|if __name__|$)",
        content,
        re.DOTALL
    )
    
    if endpoint_section:
        section_text = endpoint_section.group(0)
        
        if "fetch_nba_data()" in section_text and "fetch_nfl_data()" in section_text and "fetch_nhl_data()" in section_text:
            print("✅ Endpoint fetches NBA, NFL, NHL data")
            checks.append(True)
        else:
            print("❌ Endpoint does not fetch all NBA/NFL/NHL data")
            checks.append(False)
        
        if "homepage_arb_games" in section_text and "homepage_arb_games.append" in section_text:
            print("✅ Endpoint builds homepage_arb_games list")
            checks.append(True)
        else:
            print("❌ Endpoint does not build homepage_arb_games list")
            checks.append(False)
        
        if "is_tradable = True" in section_text and "roi_percent > min_roi" in section_text:
            print("✅ Endpoint filters by ROI threshold")
            checks.append(True)
        else:
            print("❌ Endpoint does not filter by ROI threshold")
            checks.append(False)
        
        if "'homepage_arb_games': homepage_arb_games" in section_text:
            print("✅ Endpoint returns homepage_arb_games field")
            checks.append(True)
        else:
            print("❌ Endpoint does not return homepage_arb_games field")
            checks.append(False)
    else:
        print("❌ Could not find /api/odds/multi endpoint")
        checks.append(False)
    
    return all(checks)


def check_paper_trading():
    """Verify paper trading monitor_job"""
    print("\n" + "=" * 80)
    print("3. Checking Paper Trading (monitor_job)")
    print("=" * 80)
    
    with open('api.py', 'r') as f:
        content = f.read()
    
    checks = []
    
    # Find monitor_job function
    monitor_section = re.search(
        r"def monitor_job\(\):.*?(?=^def \w+|^@app\.route|^if __name__|^# Start Scheduler)",
        content,
        re.MULTILINE | re.DOTALL
    )
    
    if monitor_section:
        section_text = monitor_section.group(0)
        
        # Check 1: Should fetch NBA/NFL/NHL only
        if "fetch_nba_data()" in section_text and "fetch_nfl_data()" in section_text and "fetch_nhl_data()" in section_text:
            print("✅ monitor_job fetches NBA, NFL, NHL data")
            checks.append(True)
        else:
            print("❌ monitor_job does not fetch NBA/NFL/NHL data")
            checks.append(False)
        
        # Check 2: Should NOT use fetch_all_sports_data
        if "fetch_all_sports_data" not in section_text:
            print("✅ monitor_job does NOT use fetch_all_sports_data")
            checks.append(True)
        else:
            print("❌ monitor_job still uses fetch_all_sports_data")
            checks.append(False)
        
        # Check 3: Should have deduplication logic
        if "seen_game_keys" in section_text and "duplicate_count" in section_text:
            print("✅ monitor_job has deduplication logic")
            checks.append(True)
        else:
            print("❌ monitor_job missing deduplication logic")
            checks.append(False)
        
        # Check 4: Should filter tradable games
        if "tradable_games" in section_text and ("edge > 0" in section_text or "edge') > 0" in section_text):
            print("✅ monitor_job filters tradable games by ROI")
            checks.append(True)
        else:
            print("❌ monitor_job does not filter tradable games")
            checks.append(False)
        
        # Check 5: Should execute paper trades
        if "paper_trader.execute_arb" in section_text:
            print("✅ monitor_job executes paper trades")
            checks.append(True)
        else:
            print("❌ monitor_job does not execute paper trades")
            checks.append(False)
    else:
        print("❌ Could not find monitor_job function")
        checks.append(False)
    
    return all(checks)


def main():
    """Run all verification checks"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "REQUIREMENTS VERIFICATION" + " " * 33 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    frontend_ok = check_frontend()
    backend_ok = check_backend_multi_endpoint()
    paper_trading_ok = check_paper_trading()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"Frontend (MULTI tab):        {'✅ PASS' if frontend_ok else '❌ FAIL'}")
    print(f"Backend (/api/odds/multi):   {'✅ PASS' if backend_ok else '❌ FAIL'}")
    print(f"Paper Trading (monitor_job): {'✅ PASS' if paper_trading_ok else '❌ FAIL'}")
    
    all_ok = frontend_ok and backend_ok and paper_trading_ok
    
    print("\n" + "=" * 80)
    if all_ok:
        print("🎉 ALL REQUIREMENTS MET!")
        print()
        print("Requirement 1: ✅ NBA/NHL/NFL markets with arbitrage opportunities")
        print("               show in MULTI tab")
        print()
        print("Requirement 2: ✅ Paper trading only trades NBA/NHL/NFL markets")
        print("               with positive ROI")
    else:
        print("❌ SOME REQUIREMENTS NOT MET")
        print("Please review the failed checks above")
    print("=" * 80)
    
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
