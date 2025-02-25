import sqlite3
from datetime import datetime

def show_game_stats():
    """显示所有游戏的最新统计信息"""
    conn = sqlite3.connect('steam_games.db')
    cursor = conn.cursor()
    
    # 从daily_stats视图获取最新统计数据
    cursor.execute('''
    SELECT g.app_id, g.name, ds.total_playtime, ds.last_record_time
    FROM games g
    JOIN daily_stats ds ON g.app_id = ds.app_id
    WHERE ds.record_date = date('now')
    ORDER BY ds.total_playtime DESC
    ''')
    
    games = cursor.fetchall()
    conn.close()
    
    # 打印统计信息
    print("\n游戏统计信息:")
    print("=" * 70)
    print(f"{'游戏ID':<12} {'总时长(小时)':<12} {'记录时间':<20} 游戏名称")
    print("-" * 70)
    
    for game in games:
        app_id, name, playtime, record_time = game
        hours = round(playtime / 60, 1)  # 转换为小时
        print(f"{app_id:<12} {hours:<12} {record_time:<20} {name}")

def show_game_history(app_id):
    """显示指定游戏的历史记录"""
    conn = sqlite3.connect('steam_games.db')
    cursor = conn.cursor()
    
    # 获取游戏的历史记录
    cursor.execute('''
    SELECT g.name, pr.playtime_total, pr.record_time
    FROM games g
    JOIN playtime_records pr ON g.app_id = pr.app_id
    WHERE g.app_id = ?
    ORDER BY pr.record_time DESC
    ''', (app_id,))
    
    records = cursor.fetchall()
    conn.close()
    
    if records:
        print(f"\n游戏 {records[0][0]} 的历史记录:")
        print("=" * 50)
        print(f"{'记录时间':<20} {'总时长(小时)':<12}")
        print("-" * 50)
        
        for name, playtime, record_time in records:
            hours = round(playtime / 60, 1)
            print(f"{record_time:<20} {hours:<12}")
    else:
        print(f"未找到ID为 {app_id} 的游戏记录")

def get_game_stats(app_id):
    """获取指定游戏的详细统计信息"""
    conn = sqlite3.connect('steam_games.db')
    cursor = conn.cursor()
    
    # 获取游戏名称
    cursor.execute('SELECT name FROM games WHERE app_id = ?', (app_id,))
    game_name = cursor.fetchone()
    if not game_name:
        print(f"未找到ID为 {app_id} 的游戏")
        conn.close()
        return
    
    game_name = game_name[0]
    print(f"\n{game_name} 的详细统计信息:")
    print("=" * 50)
    
    # 获取最后运行日期（有游戏时间的最近日期）
    cursor.execute('''
    SELECT record_date, daily_playtime
    FROM daily_stats
    WHERE app_id = ? AND daily_playtime > 0
    ORDER BY record_date DESC
    LIMIT 1
    ''', (app_id,))
    last_played = cursor.fetchone()
    if last_played:
        last_date, last_playtime = last_played
        print(f"最后运行日期: {last_date}")
        print(f"当天游戏时间: {round(last_playtime/60, 1)} 小时")
    else:
        print("最近没有游戏记录")
    
    # 获取本周游戏时间总和
    cursor.execute('''
    SELECT SUM(daily_playtime)
    FROM daily_stats
    WHERE app_id = ?
    AND record_date >= date('now', '-7 days')
    ''', (app_id,))
    weekly_time = cursor.fetchone()[0] or 0
    print(f"本周游戏时间: {round(weekly_time/60, 1)} 小时")
    
    # 获取当天游戏时间
    cursor.execute('''
    SELECT daily_playtime
    FROM daily_stats
    WHERE app_id = ? AND record_date = date('now')
    ''', (app_id,))
    today_time = cursor.fetchone()
    if today_time:
        print(f"今日游戏时间: {round(today_time[0]/60, 1)} 小时")
    else:
        print("今日暂无游戏记录")
    
    conn.close()

if __name__ == '__main__':
    # 显示所有游戏的统计信息
    show_game_stats()
    print("\n")
    
    # 显示特定游戏的详细统计
    get_game_stats(730)  # CS:GO
    print("\n")
    
    # 显示特定游戏的历史记录
    show_game_history(730)  # CS:GO的历史记录 