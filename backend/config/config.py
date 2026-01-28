# 配置文件
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 应用基本配置
class Config:
    # Flask配置
    JSON_AS_ASCII = False
    
    # 项目根目录 (向后兼容，保持原值)
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    # 数据库配置 - 直接使用backend目录下的instance文件夹
    instance_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{instance_path.replace(chr(92), "/")}/users.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 上传文件夹配置
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads')
    ALLOWED_EXTENSIONS = {'dxf', 'csv'}
    
    # 开发者密码
    DEVELOPER_PASSWORD = os.environ.get('DEVELOPER_PASSWORD', '661218')
    
    # JWT配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'yishexu-designtools-jwt-secret-key-2026')
    JWT_ACCESS_TOKEN_EXPIRES = 24 * 60 * 60
    
    # 确保上传文件夹存在
    @staticmethod
    def init_app(app):
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)

# 开发环境配置
class DevelopmentConfig(Config):
    DEBUG = True
    PORT = 8000
    HOST = '0.0.0.0'

# 生产环境配置
class ProductionConfig(Config):
    DEBUG = False
    PORT = 8000
    HOST = '0.0.0.0'

# 配置映射
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
