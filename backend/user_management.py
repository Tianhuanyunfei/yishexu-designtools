import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import uuid
from datetime import datetime
from passlib.hash import bcrypt

class UserManagementApp:
    def __init__(self, root):
        self.root = root
        self.root.title("用户管理系统")
        self.root.geometry("1000x600")
        self.root.resizable(True, True)
        
        # 设置用户数据文件路径
        # 从配置文件中读取
        try:
            # 导入配置
            import sys
            sys.path.append(os.path.dirname(__file__))
            from config.config import Config
            self.users_file = Config.USER_FILE
        except Exception as e:
            # 如果导入失败，使用默认路径
            print(f"导入配置失败: {e}")
            # 使用默认路径
            user_data_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'yishexu-designtools')
            self.users_file = os.path.join(user_data_dir, "users.json")
        print(f"用户数据文件路径: {self.users_file}")
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建顶部工具栏
        self.toolbar = ttk.Frame(self.main_frame)
        self.toolbar.pack(fill=tk.X, pady=(0, 10))
        
        # 添加按钮
        self.add_user_btn = ttk.Button(self.toolbar, text="添加用户", command=self.add_user)
        self.add_user_btn.pack(side=tk.LEFT, padx=5)
        
        self.edit_user_btn = ttk.Button(self.toolbar, text="编辑用户", command=self.edit_user)
        self.edit_user_btn.pack(side=tk.LEFT, padx=5)
        
        self.delete_user_btn = ttk.Button(self.toolbar, text="删除用户", command=self.delete_user)
        self.delete_user_btn.pack(side=tk.LEFT, padx=5)
        
        self.refresh_btn = ttk.Button(self.toolbar, text="刷新", command=self.load_users)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        
        self.config_btn = ttk.Button(self.toolbar, text="配置", command=self.open_config_window)
        self.config_btn.pack(side=tk.LEFT, padx=5)
        
        # 创建用户列表框架
        self.list_frame = ttk.Frame(self.main_frame)
        self.list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建用户列表树视图
        columns = ("id", "username", "created_at", "role", "permissions_count")
        self.user_tree = ttk.Treeview(self.list_frame, columns=columns, show="headings")
        
        # 设置列标题
        self.user_tree.heading("id", text="ID")
        self.user_tree.heading("username", text="用户名")
        self.user_tree.heading("created_at", text="创建时间")
        self.user_tree.heading("role", text="角色")
        self.user_tree.heading("permissions_count", text="权限数量")
        
        # 设置列宽
        self.user_tree.column("id", width=150)
        self.user_tree.column("username", width=100)
        self.user_tree.column("created_at", width=150)
        self.user_tree.column("role", width=80)
        self.user_tree.column("permissions_count", width=80)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(self.list_frame, orient=tk.VERTICAL, command=self.user_tree.yview)
        self.user_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.user_tree.pack(fill=tk.BOTH, expand=True)
        
        # 加载用户数据
        self.load_users()
        
    def load_users(self):
        """加载用户数据"""
        # 清空树视图
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        
        # 读取用户数据
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, "r", encoding="utf-8") as f:
                    users = json.load(f)
                
                # 添加用户到树视图
                for user_id, user_data in users.items():
                    permissions_count = len(user_data.get("permissions", []))
                    self.user_tree.insert("", tk.END, iid=user_id, values=(
                        user_id,
                        user_data["username"],
                        user_data["created_at"],
                        user_data.get("role", "user"),
                        permissions_count
                    ))
            except Exception as e:
                messagebox.showerror("错误", f"加载用户数据失败: {str(e)}")
        else:
            messagebox.showinfo("信息", "用户数据文件不存在，将创建新文件")
            # 创建空的用户数据文件
            with open(self.users_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
    
    def add_user(self):
        """添加新用户"""
        # 创建添加用户窗口
        add_window = tk.Toplevel(self.root)
        add_window.title("添加用户")
        add_window.geometry("700x700")
        add_window.resizable(True, True)
        
        # 创建表单框架
        form_frame = ttk.Frame(add_window, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # 用户名
        ttk.Label(form_frame, text="用户名:").grid(row=0, column=0, sticky=tk.W, pady=5)
        username_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=username_var, width=40).grid(row=0, column=1, pady=5)  # 此处应有表达式
        
        # 密码
        ttk.Label(form_frame, text="密码:").grid(row=1, column=0, sticky=tk.W, pady=5)
        password_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=password_var, show="*", width=40).grid(row=1, column=1, pady=5)
        
        # 角色
        ttk.Label(form_frame, text="角色:").grid(row=2, column=0, sticky=tk.W, pady=5)
        role_var = tk.StringVar(value="user")
        role_combobox = ttk.Combobox(form_frame, textvariable=role_var, values=["user", "admin"], width=37)
        role_combobox.grid(row=2, column=1, pady=5)
        
        # 权限
        ttk.Label(form_frame, text="权限:").grid(row=3, column=0, sticky=tk.W, pady=5)
        
        # 权限分类容器
        permissions_container = ttk.Frame(form_frame)
        permissions_container.grid(row=4, column=0, columnspan=2, sticky=tk.W+tk.E, pady=10)
        
        # 权限分类
        permission_categories = [
            {
                "name": "图纸绘制",
                "permissions": [
                    ("brb.drawing", "BRB图纸绘制"),
                ]
            },
            {
                "name": "设计计算",
                "permissions": [
                    ("vfd.calculate", "VFD频率计算"),
                    ("brb.calculate", "BRB结构核算"),
                ]
            },
            {
                "name": "文件系统",
                "permissions": [
                    ("file.test", "试验文件"),
                ]
            },
            {
                "name": "数据处理",
                "permissions": [
                    ("convert.dxf_to_csv", "DXF转CSV"),
                    ("convert.csv_to_dxf", "CSV转DXF"),
                    ("edit.csv", "编辑CSV文件"),
                    ("edit.excel", "编辑Excel文件"),
                ]
            },
            {
                "name": "开发中",
                "permissions": [
                    ("brb.connector.drawing", "BRB连接件绘制"),
                    ("vfd.designer", "粘滞产品设计"),
                ]
            },
            {
                "name": "系统设置",
                "permissions": [
                    ("system.settings", "系统设置"),
                ]
            }
        ]
        
        permission_vars = []
        row_idx = 0
        for category in permission_categories:
            # 创建分类标签框
            category_frame = ttk.LabelFrame(permissions_container, text=category["name"], padding="5")
            category_frame.grid(row=row_idx, column=0, sticky=tk.W+tk.E, pady=5)
            
            # 添加权限选项
            for i, (perm_value, perm_name) in enumerate(category["permissions"]):
                var = tk.BooleanVar()
                permission_vars.append((perm_value, var))
                ttk.Checkbutton(category_frame, text=perm_name, variable=var).grid(row=0, column=i, sticky=tk.W, padx=10, pady=2)
            
            row_idx += 1
        
        # 按钮框架
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        # 确定按钮
        def confirm_add():
            username = username_var.get().strip()
            password = password_var.get()
            
            if not username:
                messagebox.showerror("错误", "用户名不能为空")
                return
            
            if not password:
                messagebox.showerror("错误", "密码不能为空")
                return
            
            # 检查用户名是否已存在
            if os.path.exists(self.users_file):
                with open(self.users_file, "r", encoding="utf-8") as f:
                    users = json.load(f)
                
                for user_data in users.values():
                    if user_data["username"] == username:
                        messagebox.showerror("错误", "用户名已存在")
                        return
            else:
                users = {}
            
            # 生成递增的用户ID，从0开始
            # 找到当前最大的用户ID
            max_id = -1
            for user_id in users:
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
            
            now = datetime.utcnow().isoformat()
            
            # 生成密码哈希
            password_hash = bcrypt.hash(password)
            
            # 获取选中的权限
            selected_permissions = [perm for perm, var in permission_vars if var.get()]
            
            # 创建用户数据
            new_user = {
                "id": user_id,
                "username": username,
                "password_hash": password_hash,
                "created_at": now,
                "updated_at": now,
                "role": role_var.get(),
                "permissions": selected_permissions
            }
            
            # 添加用户到数据
            users[user_id] = new_user
            
            # 保存数据
            try:
                with open(self.users_file, "w", encoding="utf-8") as f:
                    json.dump(users, f, ensure_ascii=False, indent=2)
                
                messagebox.showinfo("成功", "用户添加成功")
                add_window.destroy()
                self.load_users()
            except Exception as e:
                messagebox.showerror("错误", f"保存用户失败: {str(e)}")
        
        ttk.Button(btn_frame, text="确定", command=confirm_add).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=add_window.destroy).pack(side=tk.LEFT, padx=10)
    
    def edit_user(self):
        """编辑现有用户"""
        # 获取选中的用户
        selected_item = self.user_tree.selection()
        if not selected_item:
            messagebox.showerror("错误", "请选择要编辑的用户")
            return
        
        user_id = selected_item[0]
        
        # 读取用户数据
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, "r", encoding="utf-8") as f:
                    users = json.load(f)
                
                if user_id not in users:
                    messagebox.showerror("错误", "用户不存在")
                    return
                
                user_data = users[user_id]
            except Exception as e:
                messagebox.showerror("错误", f"读取用户数据失败: {str(e)}")
                return
        else:
            messagebox.showerror("错误", "用户数据文件不存在")
            return
        
        # 创建编辑用户窗口
        edit_window = tk.Toplevel(self.root)
        edit_window.title("编辑用户")
        edit_window.geometry("700x700")
        edit_window.resizable(True, True)
        
        # 创建表单框架
        form_frame = ttk.Frame(edit_window, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # 用户名
        ttk.Label(form_frame, text="用户名:").grid(row=0, column=0, sticky=tk.W, pady=5)
        username_var = tk.StringVar(value=user_data["username"])
        ttk.Entry(form_frame, textvariable=username_var, width=40).grid(row=0, column=1, pady=5)
        
        # 密码（可选）
        ttk.Label(form_frame, text="密码:").grid(row=1, column=0, sticky=tk.W, pady=5)
        password_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=password_var, show="*", width=40).grid(row=1, column=1, pady=5)
        ttk.Label(form_frame, text="(留空表示不修改密码)").grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # 角色
        ttk.Label(form_frame, text="角色:").grid(row=3, column=0, sticky=tk.W, pady=5)
        role_var = tk.StringVar(value=user_data.get("role", "user"))
        role_combobox = ttk.Combobox(form_frame, textvariable=role_var, values=["user", "admin"], width=37)
        role_combobox.grid(row=3, column=1, pady=5)
        
        # 权限
        ttk.Label(form_frame, text="权限:").grid(row=4, column=0, sticky=tk.W, pady=5)
        
        # 权限分类容器
        permissions_container = ttk.Frame(form_frame)
        permissions_container.grid(row=5, column=0, columnspan=2, sticky=tk.W+tk.E, pady=10)
        
        # 权限分类
        permission_categories = [
            {
                "name": "图纸绘制",
                "permissions": [
                    ("brb.drawing", "BRB图纸绘制"),
                ]
            },
            {
                "name": "设计计算",
                "permissions": [
                    ("vfd.calculate", "VFD频率计算"),
                    ("brb.calculate", "BRB结构核算"),
                ]
            },
            {
                "name": "文件系统",
                "permissions": [
                    ("file.test", "试验文件"),
                ]
            },
            {
                "name": "数据处理",
                "permissions": [
                    ("convert.dxf_to_csv", "DXF转CSV"),
                    ("convert.csv_to_dxf", "CSV转DXF"),
                    ("edit.csv", "编辑CSV文件"),
                    ("edit.excel", "编辑Excel文件"),
                ]
            },
            {
                "name": "开发中",
                "permissions": [
                    ("brb.connector.drawing", "BRB连接件绘制"),
                    ("vfd.designer", "粘滞产品设计"),
                ]
            },
            {
                "name": "系统设置",
                "permissions": [
                    ("system.settings", "系统设置"),
                ]
            }
        ]
        
        user_permissions = user_data.get("permissions", [])
        permission_vars = []
        row_idx = 0
        for category in permission_categories:
            # 创建分类标签框
            category_frame = ttk.LabelFrame(permissions_container, text=category["name"], padding="5")
            category_frame.grid(row=row_idx, column=0, sticky=tk.W+tk.E, pady=5)
            
            # 添加权限选项
            for i, (perm_value, perm_name) in enumerate(category["permissions"]):
                var = tk.BooleanVar(value=perm_value in user_permissions)
                permission_vars.append((perm_value, var))
                ttk.Checkbutton(category_frame, text=perm_name, variable=var).grid(row=0, column=i, sticky=tk.W, padx=10, pady=2)
            
            row_idx += 1
        
        # 按钮框架
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        # 确定按钮
        def confirm_edit():
            username = username_var.get().strip()
            password = password_var.get()
            
            if not username:
                messagebox.showerror("错误", "用户名不能为空")
                return
            
            # 检查用户名是否已被其他用户使用
            for uid, udata in users.items():
                if uid != user_id and udata["username"] == username:
                    messagebox.showerror("错误", "用户名已被其他用户使用")
                    return
            
            # 更新用户数据
            now = datetime.utcnow().isoformat()
            user_data["username"] = username
            user_data["role"] = role_var.get()
            user_data["updated_at"] = now
            
            # 如果提供了新密码，更新密码
            if password:
                user_data["password_hash"] = bcrypt.hash(password)
            
            # 更新权限
            selected_permissions = [perm for perm, var in permission_vars if var.get()]
            user_data["permissions"] = selected_permissions
            
            # 保存数据
            try:
                with open(self.users_file, "w", encoding="utf-8") as f:
                    json.dump(users, f, ensure_ascii=False, indent=2)
                
                messagebox.showinfo("成功", "用户更新成功")
                edit_window.destroy()
                self.load_users()
            except Exception as e:
                messagebox.showerror("错误", f"保存用户失败: {str(e)}")
        
        ttk.Button(btn_frame, text="确定", command=confirm_edit).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=edit_window.destroy).pack(side=tk.LEFT, padx=10)
    
    def delete_user(self):
        """删除用户"""
        # 获取选中的用户
        selected_item = self.user_tree.selection()
        if not selected_item:
            messagebox.showerror("错误", "请选择要删除的用户")
            return
        
        user_id = selected_item[0]
        
        # 确认删除
        if not messagebox.askyesno("确认", "确定要删除该用户吗？"):
            return
        
        # 读取用户数据
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, "r", encoding="utf-8") as f:
                    users = json.load(f)
                
                if user_id not in users:
                    messagebox.showerror("错误", "用户不存在")
                    return
                
                # 删除用户
                del users[user_id]
                
                # 保存数据
                with open(self.users_file, "w", encoding="utf-8") as f:
                    json.dump(users, f, ensure_ascii=False, indent=2)
                
                messagebox.showinfo("成功", "用户删除成功")
                self.load_users()
            except Exception as e:
                messagebox.showerror("错误", f"删除用户失败: {str(e)}")
        else:
            messagebox.showerror("错误", "用户数据文件不存在")
    
    def open_config_window(self):
        """打开配置窗口"""
        # 创建配置窗口
        config_window = tk.Toplevel(self.root)
        config_window.title("系统配置")
        config_window.geometry("600x300")
        config_window.resizable(True, True)
        
        # 创建配置框架
        config_frame = ttk.Frame(config_window, padding="20")
        config_frame.pack(fill=tk.BOTH, expand=True)
        
        # 用户数据文件路径配置
        ttk.Label(config_frame, text="用户数据文件路径:", font=("SimHei", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=10)
        
        # 路径输入框
        path_var = tk.StringVar(value=self.users_file)
        path_entry = ttk.Entry(config_frame, textvariable=path_var, width=60)
        path_entry.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # 浏览按钮
        def browse_path():
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                title="选择用户数据文件",
                defaultextension=".json",
                filetypes=[("JSON文件", "*.json"), ("所有文件", "*")],
                initialfile="users.json"
            )
            if file_path:
                path_var.set(file_path)
        
        browse_btn = ttk.Button(config_frame, text="浏览", command=browse_path)
        browse_btn.grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        
        # 当前路径显示
        ttk.Label(config_frame, text="当前路径:", font=("SimHei", 10)).grid(row=2, column=0, sticky=tk.W, pady=5)
        current_path_label = ttk.Label(config_frame, text=self.users_file, foreground="green")
        current_path_label.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        # 按钮框架
        btn_frame = ttk.Frame(config_frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        # 保存按钮
        def save_config():
            new_path = path_var.get().strip()
            if not new_path:
                messagebox.showerror("错误", "路径不能为空")
                return
            
            # 尝试创建目录（如果不存在）
            new_dir = os.path.dirname(new_path)
            if not os.path.exists(new_dir):
                try:
                    os.makedirs(new_dir)
                except Exception as e:
                    messagebox.showerror("错误", f"创建目录失败: {str(e)}")
                    return
            
            # 尝试创建空文件（如果不存在）
            if not os.path.exists(new_path):
                try:
                    with open(new_path, "w", encoding="utf-8") as f:
                        json.dump({}, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    messagebox.showerror("错误", f"创建文件失败: {str(e)}")
                    return
            
            # 保存配置到配置文件
            try:
                # 导入配置
                import sys
                sys.path.append(os.path.dirname(__file__))
                from config.config import Config
                
                # 更新配置文件
                config_file_path = os.path.join(os.path.dirname(__file__), "config", "config.py")
                with open(config_file_path, "r", encoding="utf-8") as f:
                    config_content = f.read()
                
                # 更新USER_DATA_DIR和USER_FILE
                import re
                # 计算新的USER_DATA_DIR
                new_user_data_dir = os.path.dirname(new_path)
                # 更新配置内容
                config_content = re.sub(r'USER_DATA_DIR = .*', f"USER_DATA_DIR = r'{new_user_data_dir}'", config_content)
                config_content = re.sub(r'USER_FILE = .*', f"USER_FILE = r'{new_path}'", config_content)
                
                # 保存配置文件
                with open(config_file_path, "w", encoding="utf-8") as f:
                    f.write(config_content)
                
                # 更新当前实例的路径
                self.users_file = new_path
                print(f"用户数据文件路径已更新为: {self.users_file}")
                
                messagebox.showinfo("成功", "配置保存成功，请重启应用以生效")
                config_window.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"保存配置失败: {str(e)}")
        
        save_btn = ttk.Button(btn_frame, text="保存", command=save_config)
        save_btn.pack(side=tk.LEFT, padx=10)
        
        # 取消按钮
        cancel_btn = ttk.Button(btn_frame, text="取消", command=config_window.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=10)

if __name__ == "__main__":
    root = tk.Tk()
    app = UserManagementApp(root)
    root.mainloop()
