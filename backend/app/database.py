from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# 可用权限列表
PERMISSIONS = {
    'brb_designer': 'BRB设计',
    'brb_drawing': 'BRB图纸',
    'brb_stability': 'BRB稳定性',
    'vfd_designer': 'VFD设计',
    'vfd_period': 'VFD周期频率',
    'dxf_csv': 'DXF转CSV',
    'csv_dxf': 'CSV转DXF',
    'csv_editor': 'CSV编辑',
    'settings': '系统设置',
}

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')
    permissions = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def has_permission(self, perm):
        if self.role == 'admin':
            return True
        perm_list = self.permissions.split(',') if self.permissions else []
        return perm in perm_list
    
    def get_permissions_list(self):
        return self.permissions.split(',') if self.permissions else []
    
    def set_permissions(self, perm_list):
        self.permissions = ','.join(perm_list)
