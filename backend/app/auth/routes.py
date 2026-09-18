from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..database import User, db, PERMISSIONS
from .utils import generate_password_hash, check_password_hash, create_tokens
import re

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/permissions', methods=['GET'])
def get_all_permissions():
    """获取所有可用权限列表"""
    return jsonify({
        'status': 'success',
        'data': PERMISSIONS
    }), 200

@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        print(f"收到注册请求, content-type: {request.content_type}")
        data = request.get_json()
        print(f"解析的数据: {data}")
        
        if not data:
            return jsonify({'status': 'error', 'message': '无有效数据'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        # 验证参数
        if not username or not password:
            return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
        
        # 验证用户名长度
        if len(username) < 2 or len(username) > 50:
            return jsonify({'status': 'error', 'message': '用户名长度应在2-50个字符之间'}), 400
        
        # 验证密码长度
        if len(password) < 6:
            return jsonify({'status': 'error', 'message': '密码长度至少为6个字符'}), 400
        
        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({'status': 'error', 'message': '用户名已存在'}), 400
        
        # 生成密码哈希
        password_hash = generate_password_hash(password)
        
        # 创建新用户
        new_user = User(
            username=username,
            password_hash=password_hash
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '注册成功',
            'data': {
                'user_id': new_user.id,
                'username': new_user.username
            }
        }), 201
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'注册过程出错: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'error', 'message': '无有效数据'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        # 验证参数
        if not username or not password:
            return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
        
        # 查找用户
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'status': 'error', 'message': '用户名或密码错误'}), 401
        
        # 验证密码
        if not check_password_hash(user.password_hash, password):
            return jsonify({'status': 'error', 'message': '用户名或密码错误'}), 401
        
        # 创建访问令牌
        access_token, _ = create_tokens(user.id)
        
        return jsonify({
            'status': 'success',
            'message': '登录成功',
            'data': {
                'user_id': user.id,
                'username': user.username,
                'role': user.role,
                'permissions': user.get_permissions_list(),
                'token': access_token
            }
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'登录过程出错: {str(e)}'}), 500

@auth_bp.route('/user', methods=['GET'])
@jwt_required()
def get_user_info():
    """获取用户信息"""
    try:
        # 从JWT令牌中获取用户ID
        user_id = get_jwt_identity()
        
        # 查找用户
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return jsonify({'status': 'error', 'message': '用户不存在'}), 404
        
        return jsonify({
            'status': 'success',
            'data': {
                'user_id': user.id,
                'username': user.username,
                'role': user.role,
                'permissions': user.get_permissions_list(),
                'created_at': user.created_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'获取用户信息过程出错: {str(e)}'}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """用户退出登录"""
    try:
        # JWT是无状态的，退出登录只需在前端删除令牌即可
        # 这里可以添加令牌黑名单等功能，根据实际需求
        
        return jsonify({
            'status': 'success',
            'message': '退出登录成功'
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'退出登录过程出错: {str(e)}'}), 500

@auth_bp.route('/user/<int:user_id>/permissions', methods=['PUT'])
@jwt_required()
def update_user_permissions(user_id):
    """更新用户权限（管理员专用）"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.filter_by(id=current_user_id).first()
        
        if not current_user or current_user.role != 'admin':
            return jsonify({'status': 'error', 'message': '只有管理员可以修改权限'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '无有效数据'}), 400
        
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return jsonify({'status': 'error', 'message': '用户不存在'}), 404
        
        role = data.get('role', 'user')
        permissions = data.get('permissions', [])
        
        user.role = role
        user.set_permissions(permissions)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '权限更新成功',
            'data': {
                'user_id': user.id,
                'username': user.username,
                'role': user.role,
                'permissions': user.get_permissions_list()
            }
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'更新权限失败: {str(e)}'}), 500
