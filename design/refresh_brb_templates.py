import os
import logging
from dxf_to_csv import dxf_to_csv

# 配置日志
logging.basicConfig(filename='refresh_brb_templates.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def refresh_brb_templates():
    """
    刷新BRB模版数据
    遍历design/data目录下的所有DXF文件，将其转换为CSV文件
    """
    print("开始刷新BRB模版数据...")
    logging.info("开始刷新BRB模版数据...")
    
    # 定义数据目录路径
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    
    # 检查数据目录是否存在
    if not os.path.exists(data_dir):
        print(f"错误：数据目录 {data_dir} 不存在")
        logging.error(f"数据目录 {data_dir} 不存在")
        return False
    
    # 遍历数据目录及其子目录中的所有DXF文件
    dxf_files = []
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.lower().endswith('.dxf'):
                dxf_path = os.path.join(root, file)
                dxf_files.append(dxf_path)
    
    if not dxf_files:
        print("未找到任何DXF文件")
        logging.info("未找到任何DXF文件")
        return True
    
    print(f"找到 {len(dxf_files)} 个DXF文件，开始转换...")
    logging.info(f"找到 {len(dxf_files)} 个DXF文件，开始转换...")
    
    # 转换每个DXF文件
    success_count = 0
    failure_count = 0
    
    for dxf_path in dxf_files:
        # 构造输出CSV文件路径（与DXF文件同名，只是扩展名改为.csv）
        csv_path = os.path.splitext(dxf_path)[0] + '.csv'
        
        print(f"\n转换: {os.path.basename(dxf_path)} -> {os.path.basename(csv_path)}")
        logging.info(f"开始转换: {dxf_path} -> {csv_path}")
        
        # 调用dxf_to_csv函数进行转换
        result = dxf_to_csv(dxf_path, csv_path)
        
        if result:
            print(f"✓ 转换成功")
            logging.info(f"转换成功: {dxf_path} -> {csv_path}")
            success_count += 1
        else:
            print(f"✗ 转换失败")
            logging.error(f"转换失败: {dxf_path}")
            failure_count += 1
    
    # 输出转换结果
    print(f"\n转换完成！")
    print(f"成功: {success_count} 个文件")
    print(f"失败: {failure_count} 个文件")
    
    logging.info(f"刷新BRB模版数据完成：成功 {success_count} 个文件，失败 {failure_count} 个文件")
    
    return True

if __name__ == "__main__":
    refresh_brb_templates()