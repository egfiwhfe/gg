# Binary Arbitrage / Surebet Logic Implementation

## Overview

This document describes the strict **Binary Options / Risk-free Arbitrage / 无风险套利** logic implemented in the PolyMix arbitrage system.

## Binary Options Theory

In sports betting markets with **binary outcomes** (only two possible results):
- **Outcome A**: Team A wins
- **Outcome B**: Team B wins (which is equivalent to "Team A doesn't win")

This structure is identical to **Binary Options** where the result is either `0` or `1`.

## Cross-Market Arbitrage Strategy

For true **risk-free arbitrage** across markets, we must ensure that:

1. We buy **BOTH outcomes** (covering all possibilities)
2. We buy from **DIFFERENT markets** (to exploit price inefficiencies)
3. The **total cost < 100¢** (to guarantee profit)

### Strategy Evaluation

The system evaluates **TWO possible cross-market strategies**:

#### Strategy 1: Polymarket Away + Kalshi Home
```
Buy "Team A wins" from Polymarket (price: p_away)
Buy "Team B wins" from Kalshi (price: k_home)
Total cost = p_away × (1 + poly_fee + slippage) + k_home × (1 + kalshi_fee + slippage)
```

#### Strategy 2: Kalshi Away + Polymarket Home
```
Buy "Team A wins" from Kalshi (price: k_away)
Buy "Team B wins" from Polymarket (price: p_home)
Total cost = k_away × (1 + kalshi_fee + slippage) + p_home × (1 + poly_fee + slippage)
```

### Strategy Selection

The algorithm **picks the strategy with the LOWEST total cost**, ensuring:
- ✅ True cross-market hedging (buying from different platforms)
- ✅ Complete coverage (both outcomes purchased)
- ✅ Risk-free profit (if total cost < 100¢)

## Why This Approach Is Correct

### ❌ WRONG Approach (Old Logic)
The old logic independently selected:
- Cheapest "Team A wins" price → might pick Polymarket
- Cheapest "Team B wins" price → might also pick Polymarket

**Problem**: Both legs could end up on the SAME platform, which means:
- No cross-market arbitrage
- Exposed to single platform's fees and spread
- Not truly risk-free

### ✅ CORRECT Approach (New Logic)
The new logic evaluates complete strategies:
- Compare Strategy 1 total cost vs Strategy 2 total cost
- Select the lower-cost strategy
- Guarantee cross-market hedging

**Benefits**:
- True cross-market arbitrage
- Risk-free profit if total cost < 100¢
- Optimal platform selection

## Implementation Details

### File: `api.py`

**Function**: `_calculate_risk_free_details(poly_game, kalshi_game)`

```python
# Calculate all four effective prices
poly_away_eff = poly_away * (1 + POLYMARKET_FEE + SLIPPAGE_ESTIMATE)
poly_home_eff = poly_home * (1 + POLYMARKET_FEE + SLIPPAGE_ESTIMATE)
kalshi_away_eff = kalshi_away * (1 + KALSHI_FEE + SLIPPAGE_ESTIMATE)
kalshi_home_eff = kalshi_home * (1 + KALSHI_FEE + SLIPPAGE_ESTIMATE)

# Evaluate both strategies
strategy1_cost = poly_away_eff + kalshi_home_eff
strategy2_cost = kalshi_away_eff + poly_home_eff

# Pick lowest cost strategy
if strategy1_cost <= strategy2_cost:
    # Use Strategy 1
else:
    # Use Strategy 2
```

### File: `paper_trading.py`

**Function**: `execute_arb(game, amount_per_leg)`

The paper trading system uses the same logic in its fallback calculation, ensuring consistent arbitrage detection across the system.

## Strict Requirements

1. **Zero Price Rejection**: Prices ≤ 0 are automatically rejected
2. **Total Cost < 100¢**: Only opportunities with total cost < 100¢ are considered true arbitrage
3. **Cross-Market**: Strategies ensure different platforms for each leg
4. **Fee Inclusion**: All fees and slippage are included in calculations

## Fee Structure

- **Polymarket Fee**: 2% (0.02)
- **Kalshi Fee**: 7% (0.07)
- **Slippage Estimate**: 0.5% (0.005)

## Example

Given market prices:
- Polymarket: Away 45¢, Home 50¢
- Kalshi: Away 55¢, Home 48¢

**Strategy 1 Calculation**:
```
Poly Away: 45 × 1.025 = 46.12¢
Kalshi Home: 48 × 1.075 = 51.60¢
Total: 97.72¢ ← Selected (lower)
```

**Strategy 2 Calculation**:
```
Kalshi Away: 55 × 1.075 = 59.12¢
Poly Home: 50 × 1.025 = 51.25¢
Total: 110.38¢
```

**Result**: Strategy 1 selected
- Buy Away from Polymarket (45¢)
- Buy Home from Kalshi (48¢)
- Total cost: 97.72¢
- Guaranteed profit: 2.28¢ per unit
- ROI: 2.33%

## Testing

Run the test suite to verify the binary arbitrage logic:

```bash
python test_binary_arbitrage.py
```

The test suite covers:
1. ✅ Cross-market arbitrage detection
2. ✅ Strategy selection verification
3. ✅ No arbitrage rejection (when cost > 100¢)
4. ✅ Zero price rejection
5. ✅ Real-world examples

## Conclusion

The updated system now strictly implements **Binary Options / Surebet / 无风险套利** logic by:

1. ✅ Evaluating cross-market strategies
2. ✅ Selecting the lowest-cost strategy
3. ✅ Ensuring true risk-free arbitrage
4. ✅ Guaranteeing complete hedge coverage

This approach ensures that all arbitrage opportunities are genuine risk-free trades with guaranteed profit, regardless of which team wins.
