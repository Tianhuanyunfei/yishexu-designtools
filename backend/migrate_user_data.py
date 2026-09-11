#!/usr/bin/env python3
# 迁移用户数据到外部存储位置

import os
import json
import shutil

# 迁移用户数据
def migrate_user_data():
    print("开始迁移用户数据...")
    
    # 旧的用户数据文件路径
    old_user_file = os.path.join(os.path.dirname(__file__), "users.json")
    print(f"旧用户数据文件: {old_user_file}")
    
    # 新的用户数据文件路径
    try:
        # 导入配置
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'config'))
        from config import Config
        new_user_file = Config.USER_FILE
        print(f"新用户数据文件: {new_user_file}")
    except Exception as e:
        print(f"导入配置失败: {e}")
        print("使用默认新路径")
        # 使用默认路径
        new_user_data_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'yishexu-designtools')
        new_user_file = os.path.join(new_user_data_dir, 'users.json')
        print(f"默认新用户数据文件: {new_user_file}")
    
    # 确保新的用户数据目录存在
    new_user_data_dir = os.path.dirname(new_user_file)
    if not os.path.exists(new_user_data_dir):
        os.makedirs(new_user_data_dir)
        print(f"创建新用户数据目录: {new_user_data_dir}")
    
    # 检查旧用户数据文件是否存在
    if os.path.exists(old_user_file):
        try:
            # 读取旧用户数据
            with open(old_user_file, "r", encoding="utf-8") as f:
                old_users = json.load(f)
            print(f"读取到 {len(old_users)} 个用户数据")
            
            # 检查新用户数据文件是否存在
            if os.path.exists(new_user_file):
                # 读取新用户数据
                with open(new_user_file, "r", encoding="utf-8") as f:
                    new_users = json.load(f)
                print(f"新位置已存在 {len(new_users)} 个用户数据")
                
                # 合并用户数据
                merged_users = {**new_users, **old_users}
                print(f"合并后共有 {len(merged_users)} 个用户数据")
            else:
                # 新位置不存在用户数据，直接使用旧数据
                merged_users = old_users
                print("新位置不存在用户数据，直接使用旧数据")
            
            # 保存合并后的用户数据到新位置
            with open(new_user_file, "w", encoding="utf-8") as f:
                json.dump(merged_users, f, ensure_ascii=False, indent=2)
            print(f"用户数据已成功迁移到新位置: {new_user_file}")
            
            # 提示用户
            print("\n迁移完成!")
            print(f"用户数据现在存储在: {new_user_file}")
            print("这样在更新软件时，用户信息就不会被覆盖了。")
            
        except Exception as e:
            print(f"迁移过程出错: {e}")
            print("迁移失败，请手动迁移用户数据")
    else:
        print("旧用户数据文件不存在，无需迁移")
        # 确保新位置有一个空的用户数据文件
        if not os.path.exists(new_user_file):
            with open(new_user_file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            print(f"在新位置创建了空的用户数据文件: {new_user_file}")

if __name__ == "__main__":
    migrate_user_data()
