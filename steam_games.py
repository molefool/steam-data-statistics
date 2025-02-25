# -*- coding: utf-8 -*-
import sys
import os

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
    """更新数据库中的游戏数据"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current_time = datetime.now()
        current_date = current_time.date()
        
        for game in games_data['games']:
            # 提取游戏数据
            app_id = game['appid']
            name = game.get('name', 'Unknown')
            total_playtime = game.get('playtime_forever', 0)
            playtime_2weeks = game.get('playtime_2weeks', 0)
            
            # 更新游戏基础信息表
            cursor.execute('''
            INSERT OR REPLACE INTO games (app_id, name)
            VALUES (?, ?)
            ''', (app_id, name))
            
            # 获取今天的第一条记录，用于计算当天游戏时间
            cursor.execute('''
            SELECT playtime_total 
            FROM playtime_records 
            WHERE app_id = ? AND record_date = ?
            ORDER BY record_time ASC
            LIMIT 1
            ''', (app_id, current_date))
            
            first_record = cursor.fetchone()
            # 如果有今天的首次记录，使用它来计算当天游戏时间
            start_playtime = first_record[0] if first_record else total_playtime
            
            # 计算当天游戏时间（当前总时间 - 今天开始时的时间）
            playtime_today = total_playtime - start_playtime if first_record else 0
            
            # 插入新的时间记录
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
        
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def clean_old_records():
    """清理旧的游戏记录数据"""
    conn = sqlite3.connect('steam_games.db')
    cursor = conn.cursor()
    
    try:
        # 保留每个游戏最近7天的记录和每天的第一条和最后一条记录
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
        
        # 优化数据库
        cursor.execute('VACUUM')
        
        conn.commit()
        print(f"已清理 {deleted_count} 条历史记录")
        
    except Exception as e:
        print(f"清理数据时出错: {e}")
        conn.rollback()
    finally:
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