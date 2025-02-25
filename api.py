from flask import Blueprint, jsonify
import sqlite3
import time
from datetime import datetime
import pytz  # 添加时区支持

# 创建Blueprint而不是Flask应用
api = Blueprint('api', __name__)

def get_db_connection():
    """获取数据库连接，带重试机制"""
    max_attempts = 3
    attempt = 0
    while attempt < max_attempts:
        try:
            conn = sqlite3.connect('steam_games.db', timeout=20)
            conn.row_factory = sqlite3.Row
            # 优化数据库连接
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=10000')
            conn.execute('PRAGMA temp_store=MEMORY')
            return conn
        except sqlite3.OperationalError as e:
            attempt += 1
            if attempt == max_attempts:
                raise e
            time.sleep(1)

def get_beijing_time(utc_time_str):
    """将UTC时间转换为北京时间"""
    try:
        # 解析时间字符串
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        # 转换到北京时区
        beijing_tz = pytz.timezone('Asia/Shanghai')
        beijing_time = utc_time.astimezone(beijing_tz)
        return beijing_time
    except:
        return datetime.now(pytz.timezone('Asia/Shanghai'))

@api.route('/api/games', methods=['GET'])
def get_games():
    """获取所有游戏的基本信息，优先显示最近有变化的游戏"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 优化查询，减少子查询
        cursor.execute('''
        WITH game_stats AS (
            SELECT 
                app_id,
                SUM(CASE WHEN record_date >= date('now', '-7 days') 
                    THEN daily_playtime ELSE 0 END) as weekly_playtime,
                MAX(CASE WHEN daily_playtime > 0 
                    THEN record_date ELSE NULL END) as last_played_date
            FROM daily_stats
            GROUP BY app_id
        )
        SELECT 
            g.app_id,
            g.name,
            ds.total_playtime,
            ds.daily_playtime,
            ds.last_record_time,
            ds.record_date,
            gs.last_played_date,
            gs.weekly_playtime,
            CASE 
                WHEN ds.daily_playtime > 0 THEN 1
                ELSE 2
            END as priority
        FROM games g
        LEFT JOIN daily_stats ds ON g.app_id = ds.app_id
        LEFT JOIN game_stats gs ON g.app_id = gs.app_id
        WHERE ds.record_date >= date('now', '-7 days')
        ORDER BY 
            priority ASC,
            ds.daily_playtime DESC,
            ds.total_playtime DESC
        ''')
        
        games = cursor.fetchall()
        conn.close()
        
        return jsonify([{
            'app_id': game['app_id'],
            'name': game['name'],
            'total_hours': round(game['total_playtime'] / 60, 1) if game['total_playtime'] else 0,
            'today_hours': round(game['daily_playtime'] / 60, 1) if game['daily_playtime'] else 0,
            'weekly_hours': round(game['weekly_playtime'] / 60, 1) if game['weekly_playtime'] else 0,
            'last_played': game['last_played_date'],
            'last_record': get_beijing_time(game['last_record_time']).strftime('%Y/%m/%d %H:%M:%S'),
            'priority': game['priority']
        } for game in games])
        
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 