# 配置文件
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 应用基本配置
class Config:
    # Flask配置
    JSON_AS_ASCII = False
    
    # 项目根目录
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # 上传文件夹配置
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads')
    ALLOWED_EXTENSIONS = {'dxf', 'csv'}
    
    # 开发者密码
    DEVELOPER_PASSWORD = os.environ.get('DEVELOPER_PASSWORD', '661218')
    
    # 用户数据存储配置
    # 默认存储在用户文档目录下的yishexu-designtools文件夹中
    USER_DATA_DIR = r'D:/'
    USER_FILE = r'D:/users.json'

    # 试验文件网络存储（可通过环境变量覆盖）
    TEST_FILES_SERVER_HOST = os.environ.get('TEST_FILES_SERVER_HOST', 'WIN-5M51K63ADPF')
    TEST_FILES_DATA_PATH = os.environ.get('TEST_FILES_DATA_PATH', r'D$\data\试验')

    # 新文件中心数据目录
    WORKSPACE_DATA_DIR = os.environ.get(
        'WORKSPACE_DATA_DIR',
        os.path.join(PROJECT_ROOT, 'workspace_data')
    )

    @classmethod
    def get_test_files_network_path(cls):
        return rf'\\{cls.TEST_FILES_SERVER_HOST}\{cls.TEST_FILES_DATA_PATH}'
    
    # 确保上传文件夹存在
    @staticmethod
    def init_app(app):
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)
        # 确保用户数据目录存在
        if not os.path.exists(Config.USER_DATA_DIR):
            os.makedirs(Config.USER_DATA_DIR)
        # 确保用户数据文件存在
        if not os.path.exists(Config.USER_FILE):
            import json
            with open(Config.USER_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

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
