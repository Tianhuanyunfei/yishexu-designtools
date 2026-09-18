from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, create_refresh_token

bcrypt = Bcrypt()

def generate_password_hash(password):
    """生成密码哈希"""
    return bcrypt.generate_password_hash(password).decode('utf-8')

def check_password_hash(hashed_password, password):
    """验证密码哈希"""
    return bcrypt.check_password_hash(hashed_password, password)

def create_tokens(user_id):
    """创建访问令牌和刷新令牌"""
    access_token = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)
    return access_token, refresh_token
