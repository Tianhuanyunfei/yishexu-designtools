# 应用初始化文件
import os
import sys
from flask import Flask
from flask_cors import CORS

# 添加design目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'design'))

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 导入配置
from config.config import config

# 导入路由
from app.routes.routes import register_routes

# 创建Flask应用
def create_app(config_name=None):
    # 如果没有指定配置名称，使用环境变量中的配置或默认配置
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    # 创建Flask实例
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    
    # 初始化应用
    config[config_name].init_app(app)
    
    # 配置CORS
    CORS(app)
    
    # 注册路由
    register_routes(app)
    
    return app