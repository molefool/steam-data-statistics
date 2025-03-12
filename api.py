from flask import Blueprint, jsonify, make_response
import sqlite3
import time
from datetime import datetime
import pytz  # 添加时区支持
import logging
import os
import json

# 创建Blueprint而不是Flask应用
api = Blueprint('api', __name__)

@api.after_request
def add_header(response):
    """添加响应头以禁用缓存"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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
    """获取所有游戏的基本信息"""
    try:
        cache_file = 'game_status.json'
        if not os.path.exists(cache_file):
            return jsonify({'error': '数据正在准备中'}), 503
            
        # 读取缓存文件
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            
        # 检查数据是否过期（超过5分钟）
        cache_time = datetime.fromisoformat(cache_data['timestamp'])
        now = datetime.now()
        if (now - cache_time).total_seconds() > 300:  # 5分钟
            logging.warning("缓存数据已过期")
            
        return jsonify(cache_data['games'])
        
    except Exception as e:
        error_msg = f"获取游戏数据时出错: {str(e)}"
        logging.error(error_msg)
        logging.exception(e)
        return jsonify({'error': error_msg}), 500

@api.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM games')
        count = cursor.fetchone()[0]
        conn.close()
        return jsonify({
            'status': 'ok',
            'database': 'connected',
            'games_count': count,
            'timestamp': datetime.now(pytz.timezone('Asia/Shanghai')).isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now(pytz.timezone('Asia/Shanghai')).isoformat()
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 