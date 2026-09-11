# 用户模型
import os
import json
from datetime import datetime
import uuid

# 导入配置
from config.config import Config

class UserModel:
    def __init__(self):
        # 使用内存存储来替代MongoDB
        # 这样就不需要依赖外部数据库服务了
        self.users = {}
        # 使用外部存储路径，从配置文件中读取
        self.user_file = Config.USER_FILE
        self._load_users()
    
    def _load_users(self):
        """从文件加载用户数据"""
        try:
            if os.path.exists(self.user_file):
                with open(self.user_file, 'r', encoding='utf-8') as f:
                    users_data = json.load(f)
                    self.users = users_data
        except Exception as e:
            print(f"加载用户数据失败: {e}")
            self.users = {}
    
    def _save_users(self):
        """将用户数据保存到文件"""
        try:
            with open(self.user_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存用户数据失败: {e}")
    
    def create_user(self, username, password_hash):
        """创建新用户"""
        # 生成递增的用户ID，从0开始
        # 找到当前最大的用户ID
        max_id = -1
        for user_id in self.users:
            try:
                # 尝试将用户ID转换为整数
                current_id = int(user_id)
                if current_id > max_id:
                    max_id = current_id
            except ValueError:
                # 如果用户ID不是整数，忽略它
                pass
        
        # 新用户ID为最大ID + 1
        user_id = str(max_id + 1)
        
        user_data = {
            'id': user_id,
            'username': username,
            'password_hash': password_hash,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'role': 'user',  # 默认角色
            'permissions': ['system.settings']  # 默认拥有系统设置权限
        }
        
        self.users[user_id] = user_data
        self._save_users()
        return user_id
    
    def get_user_permissions(self, user_id):
        """获取用户权限"""
        user = self.get_user_by_id(user_id)
        if user:
            return user.get('permissions', [])
        return []
    
    def add_user_permission(self, user_id, permission):
        """添加用户权限"""
        user = self.get_user_by_id(user_id)
        if user:
            permissions = user.get('permissions', [])
            if permission not in permissions:
                permissions.append(permission)
                user['permissions'] = permissions
                user['updated_at'] = datetime.utcnow().isoformat()
                self._save_users()
                return True
        return False
    
    def remove_user_permission(self, user_id, permission):
        """移除用户权限"""
        user = self.get_user_by_id(user_id)
        if user:
            permissions = user.get('permissions', [])
            if permission in permissions:
                permissions.remove(permission)
                user['permissions'] = permissions
                user['updated_at'] = datetime.utcnow().isoformat()
                self._save_users()
                return True
        return False
    
    def set_user_permissions(self, user_id, permissions):
        """设置用户权限"""
        user = self.get_user_by_id(user_id)
        if user:
            user['permissions'] = permissions
            user['updated_at'] = datetime.utcnow().isoformat()
            self._save_users()
            return True
        return False
    
    def has_permission(self, user_id, permission):
        """检查用户是否有权限"""
        user = self.get_user_by_id(user_id)
        if user:
            permissions = user.get('permissions', [])
            return permission in permissions
        return False
    
    def get_user_by_username(self, username):
        """根据用户名获取用户"""
        for user_id, user_data in self.users.items():
            if user_data.get('username') == username:
                return user_data
        return None
    
    def get_user_by_id(self, user_id):
        """根据ID获取用户"""
        return self.users.get(user_id)
    
    def update_user(self, user_id, update_data):
        """更新用户信息"""
        if user_id in self.users:
            update_data['updated_at'] = datetime.utcnow().isoformat()
            self.users[user_id].update(update_data)
            self._save_users()
            return True
        return False
    
    def delete_user(self, user_id):
        """删除用户"""
        if user_id in self.users:
            del self.users[user_id]
            self._save_users()
            return True
        return False