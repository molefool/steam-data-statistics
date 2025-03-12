# -*- coding: utf-8 -*-
import sys
import os
import json

# 强制使用UTF-8编码
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

import requests
import sqlite3
import time
from datetime import datetime

# Steam API配置
STEAM_API_KEY = ''  # Steam API密钥
STEAM_ID = ''                      # 目标Steam用户ID
BASE_URL = 'http://api.steampowered.com'            # Steam API基础URL

def get_db_connection():
    """获取数据库连接，带重试机制"""
    max_attempts = 3
    attempt = 0
    while attempt < max_attempts:
        try:
            conn = sqlite3.connect('steam_games.db', timeout=20)
            # 添加日期时间适配器
            conn.execute('PRAGMA journal_mode=WAL')  # 使用WAL模式减少锁定
            return conn
        except sqlite3.OperationalError as e:
            attempt += 1
            if attempt == max_attempts:
                raise e
            time.sleep(1)  # 等待1秒后重试

def adapt_datetime(val):
    """datetime适配器"""
    return val.isoformat()

def adapt_date(val):
    """date适配器"""
    return val.isoformat()

def convert_datetime(val):
    """转换datetime字符串"""
    try:
        return datetime.fromisoformat(val.decode())
    except AttributeError:
        return datetime.fromisoformat(val)

def convert_date(val):
    """转换date字符串"""
    try:
        return datetime.fromisoformat(val.decode()).date()
    except AttributeError:
        return datetime.fromisoformat(val).date()

# 注册适配器和转换器
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_adapter(type(datetime.now().date()), adapt_date)
sqlite3.register_converter("datetime", convert_datetime)
sqlite3.register_converter("date", convert_date)

def get_owned_games():
    """获取用户拥有的游戏列表"""
    url = f"{BASE_URL}/IPlayerService/GetOwnedGames/v1/"
    params = {
        'key': STEAM_API_KEY,
        'steamid': STEAM_ID,
        'include_appinfo': 1,        # 包含游戏详细信息
        'include_played_free_games': 1  # 包含免费游戏
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()['response']
    except Exception as e:
        print(f"获取游戏列表时出错: {e}")
        return None

def update_database(games_data):
    """更新数据库中的游戏数据并生成缓存文件"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current_time = datetime.now()
        current_date = current_time.date()
        
        print(f"开始更新数据，当前时间: {current_time}")
        
        # 用于存储当前状态的游戏数据
        current_games = []
        
        for game in games_data['games']:
            app_id = game['appid']
            name = game.get('name', 'Unknown')
            total_playtime = game.get('playtime_forever', 0)
            playtime_2weeks = game.get('playtime_2weeks', 0)
            
            # 更新游戏基础信息
            cursor.execute('''
            INSERT OR REPLACE INTO games (app_id, name)
            VALUES (?, ?)
            ''', (app_id, name))
            
            # 获取今天的第一条记录
            cursor.execute('''
            SELECT playtime_total, record_time 
            FROM playtime_records 
            WHERE app_id = ? AND record_date = ?
            ORDER BY record_time ASC
            LIMIT 1
            ''', (app_id, current_date))
            
            first_record = cursor.fetchone()
            
            # 计算当天游戏时间
            start_playtime = first_record[0] if first_record else total_playtime
            playtime_today = total_playtime - start_playtime if first_record else 0
            
            # 插入新记录
            cursor.execute('''
            INSERT INTO playtime_records 
            (app_id, record_date, record_time, playtime_total, playtime_today, playtime_2weeks)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                app_id,
                current_date,
                current_time,
                total_playtime,
                playtime_today,
                playtime_2weeks
            ))
            
            # 获取最近7天的游戏时间统计和最后游玩日期
            cursor.execute('''
            WITH daily_stats AS (
                -- 获取每天的游戏时间变化
                SELECT 
                    record_date,
                    MAX(playtime_total) - MIN(playtime_total) as daily_playtime
                FROM playtime_records
                WHERE app_id = ?
                AND record_date >= date(?, '-7 days')
                GROUP BY record_date
                HAVING daily_playtime > 0
            )
            SELECT 
                SUM(daily_playtime) as weekly_total,
                MAX(record_date) as last_played
            FROM daily_stats
            ''', (app_id, current_date))
            
            weekly_stats = cursor.fetchone()
            weekly_playtime = weekly_stats[0] or 0
            recent_last_played = weekly_stats[1]
            
            # 如果7天内没有记录，查找历史上最后一次游玩记录
            if not recent_last_played:
                cursor.execute('''
                WITH daily_stats AS (
                    -- 获取每天的游戏时间变化
                    SELECT 
                        record_date,
                        MAX(playtime_total) - MIN(playtime_total) as daily_playtime
                    FROM playtime_records
                    WHERE app_id = ?
                    GROUP BY record_date
                    HAVING daily_playtime > 0
                )
                SELECT record_date
                FROM daily_stats
                ORDER BY record_date DESC
                LIMIT 1
                ''', (app_id,))
                
                last_played_result = cursor.fetchone()
                historical_last_played = last_played_result[0] if last_played_result else None
            else:
                historical_last_played = recent_last_played
            
            # 如果今天有游玩或最近7天有游玩，添加到当前状态
            if playtime_today > 0 or weekly_playtime > 0:
                current_games.append({
                    'app_id': app_id,
                    'name': name,
                    'total_hours': round(total_playtime / 60, 1),
                    'today_hours': round(playtime_today / 60, 1),
                    'weekly_hours': round(weekly_playtime / 60, 1),
                    'last_played': (current_date.isoformat() if playtime_today > 0 
                                  else historical_last_played),
                    'last_record': current_time.isoformat(),
                    'priority': 1 if playtime_today > 0 else 2
                })
        
        conn.commit()
        
        # 将当前状态写入缓存文件
        cache_file = 'game_status.json'
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': current_time.isoformat(),
                'games': sorted(current_games, 
                              key=lambda x: (x['priority'], -x['today_hours'], -x['weekly_hours']))
            }, f, ensure_ascii=False, indent=2)
        
        print(f"数据更新完成，已缓存 {len(current_games)} 个游戏状态")
        
    except Exception as e:
        print(f"更新数据库时出错: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def clean_old_records():
    """清理旧的游戏记录数据"""
    conn = None
    try:
        conn = sqlite3.connect('steam_games.db')
        cursor = conn.cursor()
        
        # 先删除旧记录
        cursor.execute('''
        DELETE FROM playtime_records 
        WHERE id NOT IN (
            -- 保留最近7天的所有记录
            SELECT id FROM playtime_records 
            WHERE record_date >= date('now', '-7 days')
            
            UNION
            
            -- 保留每天的第一条记录
            SELECT MIN(id) 
            FROM playtime_records 
            GROUP BY app_id, record_date
            
            UNION
            
            -- 保留每天的最后一条记录
            SELECT MAX(id) 
            FROM playtime_records 
            GROUP BY app_id, record_date
        )
        ''')
        
        # 获取删除的记录数
        deleted_count = cursor.rowcount
        conn.commit()
        
        # 关闭连接后执行VACUUM
        conn.close()
        conn = None
        
        # 重新打开连接执行VACUUM
        vacuum_conn = sqlite3.connect('steam_games.db')
        vacuum_conn.execute('VACUUM')
        vacuum_conn.close()
        
        print(f"已清理 {deleted_count} 条历史记录")
        
    except Exception as e:
        print(f"清理数据时出错: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def main():
    # 获取游戏数据
    games_data = get_owned_games()
    if games_data:
        # 更新数据库
        update_database(games_data)
        print(f"成功更新了 {len(games_data['games'])} 个游戏的数据")
        
        # 每天凌晨运行时清理旧数据
        current_hour = datetime.now().hour
        if current_hour == 0:  # 凌晨0点
            clean_old_records()
    else:
        print("获取游戏数据失败")

if __name__ == '__main__':
    main() 