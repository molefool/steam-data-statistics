import sqlite3
from datetime import datetime

def init_database():
    """初始化SQLite数据库和必要的表"""
    conn = sqlite3.connect('steam_games.db')
    cursor = conn.cursor()
    
    # 创建游戏基础信息表 - 存储游戏的基本信息
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        app_id INTEGER PRIMARY KEY,  -- 游戏ID，主键
        name TEXT NOT NULL           -- 游戏名称
    )
    ''')
    
    # 创建游戏时间记录表 - 存储游戏时间的详细记录
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS playtime_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_id INTEGER NOT NULL,
        record_date DATE NOT NULL,
        record_time DATETIME NOT NULL,
        playtime_total INTEGER NOT NULL,
        playtime_today INTEGER NOT NULL,
        playtime_2weeks INTEGER,
        FOREIGN KEY (app_id) REFERENCES games (app_id)
    )
    ''')
    
    # 添加索引以提高查询性能
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_playtime_date 
    ON playtime_records (record_date)
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_playtime_app_date 
    ON playtime_records (app_id, record_date)
    ''')
    
    # 创建每日游戏统计视图 - 用于快速查询每日统计数据
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS daily_stats AS
    SELECT 
        app_id,                                    -- 游戏ID
        record_date,                               -- 记录日期
        MAX(playtime_total) as total_playtime,     -- 当日最后总游戏时间
        MAX(playtime_today) as daily_playtime,     -- 当日游戏时间
        MAX(record_time) as last_record_time       -- 最后记录时间
    FROM playtime_records
    GROUP BY app_id, record_date                   -- 按游戏和日期分组
    ''')
    
    conn.commit()
    conn.close()
    
    print("数据库初始化完成")

if __name__ == '__main__':
    init_database() 