import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import hashlib
from datetime import datetime
import os

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

class UserManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("用户管理 - 后台管理工具")
        self.root.geometry("1100x700")
        self.root.resizable(True, True)
        
        self.db_path = os.path.join(os.path.dirname(__file__), 'instance', 'users.db')
        self.conn = None
        self.cursor = None
        
        self.setup_ui()
        self.connect_db()
        self.load_users()
    
    def connect_db(self):
        try:
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)
            
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            self.create_table()
        except Exception as e:
            messagebox.showerror("数据库错误", f"连接数据库失败: {e}")
    
    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'user',
                permissions TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in self.cursor.fetchall()]
        
        if 'role' not in columns:
            self.cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'")
        if 'permissions' not in columns:
            self.cursor.execute("ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT ''")
        
        self.conn.commit()
        
        self.create_default_admin()
    
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_default_admin(self):
        try:
            self.cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
            if not self.cursor.fetchone():
                admin_password = self.hash_password('admin123')
                self.cursor.execute(
                    "INSERT INTO users (username, password_hash, role, permissions) VALUES (?, ?, ?, ?)",
                    ('admin', admin_password, 'admin', '')
                )
                self.conn.commit()
                print("已创建默认管理员账户: admin / admin123")
        except Exception as e:
            print(f"创建默认管理员失败: {e}")
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="用户管理系统", font=("Microsoft YaHei", 18, "bold"))
        title_label.pack(pady=(0, 10))
        
        search_frame = ttk.LabelFrame(main_frame, text="搜索", padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="用户名:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(search_frame, text="搜索", command=self.search_users).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="显示全部", command=self.load_users).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="刷新", command=self.load_users).pack(side=tk.LEFT, padx=5)
        
        tree_frame = ttk.LabelFrame(main_frame, text="用户列表", padding="10")
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        columns = ("ID", "用户名", "角色", "权限", "创建时间", "更新时间")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        
        self.tree.heading("ID", text="ID")
        self.tree.heading("用户名", text="用户名")
        self.tree.heading("角色", text="角色")
        self.tree.heading("权限", text="权限")
        self.tree.heading("创建时间", text="创建时间")
        self.tree.heading("更新时间", text="更新时间")
        
        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("用户名", width=100, anchor="center")
        self.tree.column("角色", width=80, anchor="center")
        self.tree.column("权限", width=200, anchor="center")
        self.tree.column("创建时间", width=130, anchor="center")
        self.tree.column("更新时间", width=130, anchor="center")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(button_frame, text="添加用户", command=self.add_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="编辑用户", command=self.edit_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="重置密码", command=self.reset_password).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="管理权限", command=self.manage_permissions).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除用户", command=self.delete_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="导出用户", command=self.export_users).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="关闭", command=self.root.quit).pack(side=tk.RIGHT, padx=5)
        
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X)
        
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var)
        status_label.pack(side=tk.LEFT)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def load_users(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        try:
            self.cursor.execute("SELECT id, username, role, permissions, created_at, updated_at FROM users ORDER BY id DESC")
            rows = self.cursor.fetchall()
            
            for row in rows:
                role = row[2] if row[2] else 'user'
                perms = row[3] if row[3] else ''
                perm_names = []
                if perms:
                    for p in perms.split(','):
                        p = p.strip()
                        if p in PERMISSIONS:
                            perm_names.append(PERMISSIONS[p])
                        elif p:
                            perm_names.append(p)
                perm_display = ','.join(perm_names) if perm_names else '无'
                if role == 'admin':
                    perm_display = '管理员(全部权限)'
                
                formatted_row = (
                    row[0],
                    row[1],
                    '管理员' if role == 'admin' else '普通用户',
                    perm_display,
                    row[4] if row[4] else "",
                    row[5] if row[5] else ""
                )
                self.tree.insert("", tk.END, values=formatted_row)
            
            self.status_var.set(f"共 {len(rows)} 个用户")
        except Exception as e:
            messagebox.showerror("错误", f"加载用户失败: {e}")
    
    def search_users(self):
        search_term = self.search_var.get().strip()
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        try:
            if search_term:
                self.cursor.execute(
                    "SELECT id, username, role, permissions, created_at, updated_at FROM users WHERE username LIKE ? ORDER BY id DESC",
                    (f"%{search_term}%",)
                )
            else:
                self.cursor.execute("SELECT id, username, role, permissions, created_at, updated_at FROM users ORDER BY id DESC")
            
            rows = self.cursor.fetchall()
            
            for row in rows:
                role = row[2] if row[2] else 'user'
                perms = row[3] if row[3] else ''
                perm_names = []
                if perms:
                    for p in perms.split(','):
                        p = p.strip()
                        if p in PERMISSIONS:
                            perm_names.append(PERMISSIONS[p])
                        elif p:
                            perm_names.append(p)
                perm_display = ','.join(perm_names) if perm_names else '无'
                if role == 'admin':
                    perm_display = '管理员(全部权限)'
                
                formatted_row = (
                    row[0],
                    row[1],
                    '管理员' if role == 'admin' else '普通用户',
                    perm_display,
                    row[4] if row[4] else "",
                    row[5] if row[5] else ""
                )
                self.tree.insert("", tk.END, values=formatted_row)
            
            self.status_var.set(f"找到 {len(rows)} 个用户")
        except Exception as e:
            messagebox.showerror("错误", f"搜索用户失败: {e}")
    
    def on_tree_double_click(self, event):
        self.edit_user()
    
    def add_user(self):
        dialog = UserDialog(self.root, "添加用户", None)
        if dialog.result:
            username = dialog.username_var.get().strip()
            password = dialog.password_var.get()
            confirm_password = dialog.confirm_password_var.get()
            
            if not username:
                messagebox.showerror("错误", "用户名不能为空")
                return
            
            if len(username) < 2:
                messagebox.showerror("错误", "用户名至少需要2个字符")
                return
            
            if len(password) < 6:
                messagebox.showerror("错误", "密码至少需要6个字符")
                return
            
            if password != confirm_password:
                messagebox.showerror("错误", "两次输入的密码不一致")
                return
            
            try:
                password_hash = self.hash_password(password)
                self.cursor.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash)
                )
                self.conn.commit()
                messagebox.showinfo("成功", f"用户 '{username}' 添加成功！")
                self.load_users()
            except sqlite3.IntegrityError:
                messagebox.showerror("错误", f"用户名 '{username}' 已存在")
            except Exception as e:
                messagebox.showerror("错误", f"添加用户失败: {e}")
    
    def edit_user(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请选择一个用户")
            return
        
        item = self.tree.item(selected[0])
        user_id = item["values"][0]
        current_username = item["values"][1]
        
        self.cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        result = self.cursor.fetchone()
        if result:
            current_username = result[0]
        
        dialog = UserDialog(self.root, "编辑用户", current_username)
        if dialog.result:
            new_username = dialog.username_var.get().strip()
            
            if not new_username:
                messagebox.showerror("错误", "用户名不能为空")
                return
            
            if len(new_username) < 2:
                messagebox.showerror("错误", "用户名至少需要2个字符")
                return
            
            try:
                if new_username != current_username:
                    self.cursor.execute(
                        "UPDATE users SET username = ? WHERE id = ?",
                        (new_username, user_id)
                    )
                self.conn.commit()
                messagebox.showinfo("成功", f"用户信息已更新！")
                self.load_users()
            except sqlite3.IntegrityError:
                messagebox.showerror("错误", f"用户名 '{new_username}' 已存在")
            except Exception as e:
                messagebox.showerror("错误", f"更新用户失败: {e}")
    
    def reset_password(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请选择一个用户")
            return
        
        item = self.tree.item(selected[0])
        user_id = item["values"][0]
        username = item["values"][1]
        
        dialog = PasswordDialog(self.root, f"重置密码 - {username}")
        if dialog.result:
            new_password = dialog.password_var.get()
            confirm_password = dialog.confirm_password_var.get()
            
            if len(new_password) < 6:
                messagebox.showerror("错误", "密码至少需要6个字符")
                return
            
            if new_password != confirm_password:
                messagebox.showerror("错误", "两次输入的密码不一致")
                return
            
            try:
                password_hash = self.hash_password(new_password)
                self.cursor.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (password_hash, user_id)
                )
                self.conn.commit()
                messagebox.showinfo("成功", f"用户 '{username}' 的密码已重置！")
            except Exception as e:
                messagebox.showerror("错误", f"重置密码失败: {e}")
    
    def manage_permissions(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请选择一个用户")
            return
        
        item = self.tree.item(selected[0])
        user_id = item["values"][0]
        username = item["values"][1]
        
        try:
            self.cursor.execute("SELECT role, permissions FROM users WHERE id = ?", (user_id,))
            result = self.cursor.fetchone()
            if result:
                current_role = result[0] if result[0] else 'user'
                current_permissions = result[1] if result[1] else ''
            else:
                current_role = 'user'
                current_permissions = ''
        except Exception as e:
            messagebox.showerror("错误", f"获取用户权限失败: {e}")
            return
        
        dialog = PermissionsDialog(self.root, f"管理权限 - {username}", current_role, current_permissions)
        if dialog.result:
            new_role = dialog.role_var.get()
            new_permissions = dialog.get_selected_permissions()
            
            try:
                perm_string = ','.join(new_permissions) if new_role != 'admin' else ''
                self.cursor.execute(
                    "UPDATE users SET role = ?, permissions = ? WHERE id = ?",
                    (new_role, perm_string, user_id)
                )
                self.conn.commit()
                messagebox.showinfo("成功", f"用户 '{username}' 的权限已更新！")
                self.load_users()
            except Exception as e:
                messagebox.showerror("错误", f"更新权限失败: {e}")
    
    def delete_user(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请选择一个用户")
            return
        
        item = self.tree.item(selected[0])
        user_id = item["values"][0]
        username = item["values"][1]
        
        if not messagebox.askyesno("确认", f"确定要删除用户 '{username}' 吗？\n此操作不可撤销！"):
            return
        
        try:
            self.cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self.conn.commit()
            messagebox.showinfo("成功", f"用户 '{username}' 已删除！")
            self.load_users()
        except Exception as e:
            messagebox.showerror("错误", f"删除用户失败: {e}")
    
    def export_users(self):
        try:
            self.cursor.execute("SELECT id, username, created_at, updated_at FROM users ORDER BY id")
            rows = self.cursor.fetchall()
            
            if not rows:
                messagebox.showwarning("提示", "没有用户数据可导出")
                return
            
            export_content = "用户列表导出\n" + "="*60 + "\n\n"
            export_content += f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            export_content += f"用户总数: {len(rows)}\n\n"
            export_content += "-"*60 + "\n"
            
            for row in rows:
                export_content += f"ID: {row[0]}\n"
                export_content += f"用户名: {row[1]}\n"
                export_content += f"创建时间: {row[2]}\n"
                export_content += f"更新时间: {row[3]}\n"
                export_content += "-"*30 + "\n"
            
            file_path = os.path.join(os.path.dirname(__file__), 'users_export.txt')
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(export_content)
            
            messagebox.showinfo("成功", f"用户数据已导出到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")
    
    def on_closing(self):
        if self.conn:
            self.conn.close()
        self.root.destroy()


class UserDialog:
    def __init__(self, parent, title, current_username=None):
        self.result = False
        self.current_username = current_username
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("350x200")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="用户名:").grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        self.username_var = tk.StringVar(value=current_username if current_username else "")
        self.username_entry = ttk.Entry(frame, textvariable=self.username_var, width=30)
        self.username_entry.grid(row=0, column=1, pady=(0, 10), padx=(10, 0))
        
        if current_username is None:
            ttk.Label(frame, text="密码:").grid(row=1, column=0, sticky=tk.W, pady=(0, 10))
            self.password_var = tk.StringVar()
            self.password_entry = ttk.Entry(frame, textvariable=self.password_var, show="*", width=30)
            self.password_entry.grid(row=1, column=1, pady=(0, 10), padx=(10, 0))
            
            ttk.Label(frame, text="确认密码:").grid(row=2, column=0, sticky=tk.W, pady=(0, 10))
            self.confirm_password_var = tk.StringVar()
            self.confirm_password_entry = ttk.Entry(frame, textvariable=self.confirm_password_var, show="*", width=30)
            self.confirm_password_entry.grid(row=2, column=1, pady=(0, 10), padx=(10, 0))
        
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(button_frame, text="确定", command=self.ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        self.dialog.bind("<Return>", lambda e: self.ok())
        self.dialog.bind("<Escape>", lambda e: self.cancel())
        
        self.dialog.geometry("+{}+{}".format(
            parent.winfo_x() + 150,
            parent.winfo_y() + 100
        ))
        
        self.username_entry.focus_set()
        self.dialog.wait_window()
    
    def ok(self):
        self.result = True
        self.dialog.destroy()
    
    def cancel(self):
        self.result = False
        self.dialog.destroy()


class PermissionsDialog:
    def __init__(self, parent, title, current_role, current_permissions):
        self.result = False
        self.current_role = current_role
        self.current_permissions = current_permissions.split(',') if current_permissions else []
        self.permission_vars = {}
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="角色:").grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        self.role_var = tk.StringVar(value=current_role)
        role_combo = ttk.Combobox(frame, textvariable=self.role_var, values=['user', 'admin'], state='readonly', width=27)
        role_combo.grid(row=0, column=1, pady=(0, 10), padx=(10, 0))
        role_combo.bind("<<ComboboxSelected>>", self.on_role_changed)
        
        ttk.Label(frame, text="权限分配:").grid(row=1, column=0, sticky=tk.NW, pady=(0, 10))
        
        self.perms_frame = ttk.Frame(frame)
        self.perms_frame.grid(row=1, column=1, pady=(0, 10), padx=(10, 0))
        
        self.create_permission_checkboxes()
        
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(button_frame, text="全选", command=self.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="全不选", command=self.deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="确定", command=self.ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        self.dialog.bind("<Return>", lambda e: self.ok())
        self.dialog.bind("<Escape>", lambda e: self.cancel())
        
        self.dialog.geometry("+{}+{}".format(
            parent.winfo_x() + 150,
            parent.winfo_y() + 100
        ))
        
        self.dialog.wait_window()
    
    def create_permission_checkboxes(self):
        for i, (perm_key, perm_name) in enumerate(PERMISSIONS.items()):
            var = tk.BooleanVar(value=perm_key in self.current_permissions)
            self.permission_vars[perm_key] = var
            cb = ttk.Checkbutton(self.perms_frame, text=perm_name, variable=var)
            cb.grid(row=i // 2, column=i % 2, sticky=tk.W, padx=5, pady=2)
    
    def on_role_changed(self, event):
        if self.role_var.get() == 'admin':
            for var in self.permission_vars.values():
                var.set(True)
            for cb in self.perms_frame.winfo_children():
                if isinstance(cb, ttk.Checkbutton):
                    cb.state(['disabled'])
        else:
            for cb in self.perms_frame.winfo_children():
                if isinstance(cb, ttk.Checkbutton):
                    cb.state(['!disabled'])
    
    def select_all(self):
        if self.role_var.get() != 'admin':
            for var in self.permission_vars.values():
                var.set(True)
    
    def deselect_all(self):
        if self.role_var.get() != 'admin':
            for var in self.permission_vars.values():
                var.set(False)
    
    def get_selected_permissions(self):
        return [perm_key for perm_key, var in self.permission_vars.items() if var.get()]
    
    def ok(self):
        if self.role_var.get() != 'admin':
            selected = self.get_selected_permissions()
            if not selected:
                messagebox.showwarning("提示", "请至少选择一个权限")
                return
        self.result = True
        self.dialog.destroy()
    
    def cancel(self):
        self.result = False
        self.dialog.destroy()


class PasswordDialog:
    def __init__(self, parent, title):
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("300x150")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="新密码:").grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(frame, textvariable=self.password_var, show="*", width=25)
        self.password_entry.grid(row=0, column=1, pady=(0, 10), padx=(10, 0))
        
        ttk.Label(frame, text="确认密码:").grid(row=1, column=0, sticky=tk.W, pady=(0, 10))
        self.confirm_password_var = tk.StringVar()
        self.confirm_password_entry = ttk.Entry(frame, textvariable=self.confirm_password_var, show="*", width=25)
        self.confirm_password_entry.grid(row=1, column=1, pady=(0, 10), padx=(10, 0))
        
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(button_frame, text="确定", command=self.ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        self.dialog.bind("<Return>", lambda e: self.ok())
        self.dialog.bind("<Escape>", lambda e: self.cancel())
        
        self.dialog.geometry("+{}+{}".format(
            parent.winfo_x() + 175,
            parent.winfo_y() + 150
        ))
        
        self.password_entry.focus_set()
        self.dialog.wait_window()
    
    def ok(self):
        self.result = True
        self.dialog.destroy()
    
    def cancel(self):
        self.result = False
        self.dialog.destroy()


def main():
    root = tk.Tk()
    app = UserManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
