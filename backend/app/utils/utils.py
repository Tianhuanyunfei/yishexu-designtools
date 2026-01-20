# 工具函数
import os
from werkzeug.utils import secure_filename
from config.config import Config

# 辅助函数：检查文件类型
def allowed_file(filename, allowed_extensions=None):
    if allowed_extensions is None:
        allowed_extensions = Config.ALLOWED_EXTENSIONS
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# 辅助函数：验证文件路径是否安全
def validate_file_path(file_path, project_root=None):
    """
    验证文件路径是否安全，防止目录遍历攻击
    
    Args:
        file_path: 要验证的文件路径
        project_root: 项目根目录，默认为Config.PROJECT_ROOT
        
    Returns:
        tuple: (是否安全, 绝对路径)
    """
    if project_root is None:
        project_root = Config.PROJECT_ROOT
        
    abs_file_path = os.path.abspath(file_path)
    is_safe = abs_file_path.startswith(project_root) and os.path.exists(abs_file_path)
    
    return is_safe, abs_file_path
