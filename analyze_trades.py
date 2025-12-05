#!/usr/bin/env python3
import json

with open("paper_trading_data.json", "r") as f:
    data = json.load(f)

print("=== Paper Trading Summary ===")
print(f"Balance: ${data['balance']:.2f}")
print(f"Initial Balance: ${data['initial_balance']:.2f}")
print(f"Total Bets: {len(data['bets'])}")

print("\n=== All Trades with ROI ===")
for bet in data["bets"]:
    game = bet["game"]
    roi = bet["roi_percent"]
    profit = bet["profit"]
    sport = bet["sport"]
    print(f"{game} [{sport}]: ROI={roi:.2f}%, Profit=${profit:.2f}")

print("\n=== ROI Analysis ===")
highest_roi_bet = max(data["bets"], key=lambda x: x["roi_percent"])
print(f"Highest ROI: {highest_roi_bet['game']} - {highest_roi_bet['roi_percent']:.2f}%")

# Check if any bet has ROI >= 10.38%
high_roi_bets = [bet for bet in data["bets"] if bet["roi_percent"] >= 10.38]
print(f"Bets with ROI >= 10.38%: {len(high_roi_bets)}")
for bet in high_roi_bets:
    print(f"  - {bet['game']}: {bet['roi_percent']:.2f}%")