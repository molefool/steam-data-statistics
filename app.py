from flask import Flask, render_template
from api import api
import threading
import time
import subprocess
import logging
import sys
import os
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('steam_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

# 注册Blueprint
app.register_blueprint(api)

@app.route('/')
def index():
    """渲染主页"""
    return render_template('index.html')

def run_data_collection():
    """运行数据收集脚本的函数"""
    while True:
        try:
            logging.info("开始执行数据收集...")
            start_time = time.time()
            
            # 添加重试机制
            max_attempts = 3
            attempt = 0
            success = False
            
            while attempt < max_attempts and not success:
                try:
                    process = subprocess.Popen(
                        [sys.executable, 'steam_games.py'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        encoding='utf-8',
                        errors='replace',
                        cwd=os.path.dirname(os.path.abspath(__file__))
                    )
                    
                    stdout, stderr = process.communicate()
                    
                    if process.returncode == 0:
                        execution_time = time.time() - start_time
                        logging.info(f"数据收集完成，耗时: {execution_time:.2f}秒")
                        if stdout:
                            logging.info(f"输出: {stdout.strip()}")
                        success = True
                    else:
                        attempt += 1
                        if attempt == max_attempts:
                            logging.error(f"数据收集失败: {stderr}")
                        else:
                            logging.warning(f"第{attempt}次尝试失败，等待重试...")
                            time.sleep(5)  # 等待5秒后重试
                            
                except Exception as e:
                    attempt += 1
                    if attempt == max_attempts:
                        logging.error(f"执行数据收集时发生错误: {str(e)}")
                    time.sleep(5)
                    
        except Exception as e:
            logging.error(f"执行数据收集时发生错误: {str(e)}")
            
        time.sleep(1200)  # 20分钟

def start_data_collection_thread():
    """启动数据收集线程"""
    collection_thread = threading.Thread(target=run_data_collection, daemon=True)
    collection_thread.start()
    logging.info("数据收集线程已启动")

if __name__ == '__main__':
    # 设置工作目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 启动数据收集线程
    start_data_collection_thread()
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=False) 