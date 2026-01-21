import json
import os
from brb_tube_layout import TubeLayoutGenerator

# 读取 JSON 文件
json_file = "d:\\Python\\yishexu-designtools\\backend\\design\\宜宾赛事中心.json"
with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 提取项目名称和参数表
project_name = data.get('project_name', 'unnamed')
param_tables = data.get('param_tables', [])

# 创建 TubeLayoutGenerator 实例
generator = TubeLayoutGenerator()

# 生成方管排布图
file_paths = generator.generate_tube_layout(project_name, param_tables)

# 打印生成的文件路径
print("生成的文件路径:")
for file_path in file_paths:
    print(file_path)
