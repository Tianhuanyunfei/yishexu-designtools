# 日志配置模块
import os
import logging
from logging.handlers import RotatingFileHandler

# 获取项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 日志目录
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件路径
APP_LOG_FILE = os.path.join(LOG_DIR, 'app.log')
# 功能模块日志文件
FUNCTION_LOG_FILE = os.path.join(LOG_DIR, 'function.log')
# 功能模块报警日志文件
FUNCTION_ALARM_LOG_FILE = os.path.join(LOG_DIR, 'function_alarm.log')

# 日志格式
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(module)s - %(message)s'

# 创建不同的日志记录器
def create_logger(name, log_file, level=logging.INFO):
    """
    创建并配置日志记录器
    :param name: 日志记录器名称
    :param log_file: 日志文件路径
    :param level: 日志级别
    :return: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加处理器
    if not logger.handlers:
        # 文件处理器
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# 应用日志记录器
app_logger = create_logger('app', APP_LOG_FILE)

# 功能模块日志记录器 - 记录各功能使用情况
function_logger = create_logger('function', FUNCTION_LOG_FILE)

# 功能模块报警日志记录器 - 记录功能使用过程中出现的问题
function_alarm_logger = create_logger('function_alarm', FUNCTION_ALARM_LOG_FILE, level=logging.WARNING)