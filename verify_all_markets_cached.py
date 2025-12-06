#!/usr/bin/env python3
"""
Verify that all fetched markets are written to all_sports_cache.json
"""
import json
import os
from datetime import datetime
from api import fetch_all_sports_data

def verify_cache():
    print("=" * 80)
    print("验证所有获取的市场都写入到 all_sports_cache.json")
    print("=" * 80)
    
    # 清除旧缓存
    if os.path.exists('all_sports_cache.json'):
        os.remove('all_sports_cache.json')
        print("✅ 已清除旧缓存文件")
    
    # 获取新数据
    print("\n获取所有运动数据...")
    result = fetch_all_sports_data(force_refresh=True)
    
    # 验证结果结构
    print("\n验证返回的数据结构:")
    required_fields = [
        'success', 'timestamp', 'stats', 'matched_games',
        'arb_opportunities', 'homepage_games', 'all_polymarket_games',
        'all_kalshi_games'
    ]
    
    for field in required_fields:
        has_field = field in result
        status = "✅" if has_field else "❌"
        print(f"  {status} {field}")
        if not has_field:
            print(f"     错误: 缺少必需字段 '{field}'")
            return False
    
    # 验证数据完整性
    print("\n验证数据完整性:")
    poly_count = len(result.get('all_polymarket_games', []))
    kalshi_count = len(result.get('all_kalshi_games', []))
    matched_count = len(result.get('matched_games', []))
    
    print(f"  - Polymarket 游戏总数: {poly_count}")
    print(f"  - Kalshi 游戏总数: {kalshi_count}")
    print(f"  - 匹配的游戏: {matched_count}")
    
    if poly_count == 0:
        print("  ⚠️  警告: 没有获取到 Polymarket 游戏")
    if kalshi_count == 0:
        print("  ⚠️  警告: 没有获取到 Kalshi 游戏")
    
    # 验证缓存文件
    print("\n验证缓存文件:")
    if not os.path.exists('all_sports_cache.json'):
        print("  ❌ 缓存文件不存在")
        return False
    
    file_size = os.path.getsize('all_sports_cache.json')
    print(f"  ✅ 缓存文件存在，大小: {file_size / 1024:.2f} KB")
    
    # 读取缓存并验证内容
    with open('all_sports_cache.json', 'r') as f:
        cached = json.load(f)
    
    cached_poly_count = len(cached.get('all_polymarket_games', []))
    cached_kalshi_count = len(cached.get('all_kalshi_games', []))
    
    print(f"\n验证缓存内容:")
    print(f"  - 缓存中的 Polymarket 游戏: {cached_poly_count}")
    print(f"  - 缓存中的 Kalshi 游戏: {cached_kalshi_count}")
    
    if cached_poly_count != poly_count:
        print(f"  ❌ 错误: 缓存中的 Polymarket 游戏数量 ({cached_poly_count}) 与获取的不一致 ({poly_count})")
        return False
    
    if cached_kalshi_count != kalshi_count:
        print(f"  ❌ 错误: 缓存中的 Kalshi 游戏数量 ({cached_kalshi_count}) 与获取的不一致 ({kalshi_count})")
        return False
    
    print("  ✅ 缓存内容与获取的数据一致")
    
    # 显示一些示例数据
    print("\n示例数据:")
    if cached.get('all_polymarket_games'):
        print("  前3个 Polymarket 游戏:")
        for i, game in enumerate(cached['all_polymarket_games'][:3], 1):
            print(f"    {i}. {game.get('away_team')} @ {game.get('home_team')}")
            print(f"       Sport: {game.get('sport')}, Away: {game.get('away_prob')}%, Home: {game.get('home_prob')}%")
    
    if cached.get('all_kalshi_games'):
        print("\n  前3个 Kalshi 游戏:")
        for i, game in enumerate(cached['all_kalshi_games'][:3], 1):
            print(f"    {i}. {game.get('away_team')} @ {game.get('home_team')}")
            print(f"       Sport: {game.get('sport')}, Away: {game.get('away_prob')}%, Home: {game.get('home_prob')}%")
    
    print("\n" + "=" * 80)
    print("✅ 所有验证通过！所有获取的市场都已正确写入缓存。")
    print("=" * 80)
    return True

if __name__ == '__main__':
    success = verify_cache()
    exit(0 if success else 1)
