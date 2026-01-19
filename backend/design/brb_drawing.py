import csv
import logging
import os  # 新增：导入os模块用于设置工作目录

# 修复导入路径
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from csv_to_dxf import csv_to_dxf


"""更新数据"""
# 王工
def update_data1(csv_data, input_param, width, height, thick, force, tube_width, tube_thickness, weld, core_material, table):
    """通用的CSV数据更新函数"""
    try:
        # 获取列名
        header = csv_data[0]

        # 生成列名和索引的映射字典
        column_index_map = {col_name: header.index(col_name) for col_name in header}

        # 主视图，长度数量说明
        result_str = ''
        product_quantity = 0
        count = 0
        total_count = len(table)
        for index, (length, quantity) in enumerate(table):
            result_str += f'L={length}-{quantity}件, '
            product_quantity += quantity
            count += 1
            if count % 4 == 0 and index < total_count - 1:
                result_str += '\P'
        result_str = result_str.rstrip(' ， ')
        csv_data[81][column_index_map['值']] = f'\W0.7;\T1.1;{result_str}\P共计{product_quantity}件'

        # 端面
        update_cell_value(csv_data, 149, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 150, column_index_map, '覆盖值', width)
        update_cell_value(csv_data, 151, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 152, column_index_map, '覆盖值', height - thick - thick)
        update_cell_value(csv_data, 153, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 154, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 155, column_index_map, '覆盖值', tube_width)
        update_cell_value(csv_data, 156, column_index_map, '覆盖值', tube_width)
        
        # 方管厚度
        update_cell_value(csv_data, 111, column_index_map, '覆盖值', tube_thickness)

        # 端面焊缝
        update_cell_value(csv_data, 110, column_index_map, '值', f'\T1.1;{format_number(weld)}')

        # 耗能面设置
       
        update_cell_value(csv_data, 185, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 186, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 187, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 188, column_index_map, '覆盖值', height)
        update_cell_value(csv_data, 189, column_index_map, '覆盖值', width)

        # 连接板尺寸
        update_cell_value(csv_data, 201, column_index_map, '覆盖值', (width - thick) / 2)

        # 连接板数量
        update_cell_value(csv_data, 199, column_index_map, '值', f'\W0.7;\T1.1;连接板 H={format_number(thick)}-{format_number(product_quantity * 4)}件')

        # 挡板尺寸
        update_cell_value(csv_data, 216, column_index_map, '覆盖值', width + 5)
        update_cell_value(csv_data, 217, column_index_map, '覆盖值', thick + 5)
        update_cell_value(csv_data, 218, column_index_map, '覆盖值', thick + 5)
        update_cell_value(csv_data, 219, column_index_map, '覆盖值', thick + 5)
        update_cell_value(csv_data, 222, column_index_map, '覆盖值', thick + 5)
        update_cell_value(csv_data, 223, column_index_map, '覆盖值', height - thick - thick - 5)
        update_cell_value(csv_data, 206, column_index_map, '覆盖值', tube_width + 20 if tube_width != 200 else tube_width + 15)
        update_cell_value(csv_data, 209, column_index_map, '覆盖值', tube_width + 20 if tube_width != 200 else tube_width + 15)

        # 挡板焊缝
        update_cell_value(csv_data, 245, column_index_map, '值', f'\T1.1;C{format_number(weld)}')
        # 挡板数量
        update_cell_value(csv_data, 207, column_index_map, '值', f'\W0.7;\T1.1;挡板H=6-{format_number(product_quantity * 2)}件')

        # 标题栏，项目名称
        cell_with = 540 # 单元格宽度
        max_width = cell_with-20 # 字符串最大限制宽度
        dynamic_multiplier, true_length = calculate_dynamic_width(input_param, max_width) # 对项目名称字符串进行缩放，并返回倍率和实际宽度
        update_cell_value(csv_data, 292, column_index_map, '值', f'\W{dynamic_multiplier:.2f};\T1.1;{input_param}') # 更新值单元格值
        # 标题栏，项目名称，位置置中
        update_cell_value(csv_data, 292, column_index_map, '位置 X', - cell_with / 2 - true_length / 2) # 更新位置X单元格值
        
        # 标题栏，产品型号
        update_cell_value(csv_data, 294, column_index_map, '值', f'\W0.7;\T1.1;YSX-BRB-{force}-L')

        # 芯板材料
        update_cell_value(csv_data, 297, column_index_map, '值', f'芯板材料：{core_material}')

    except (IndexError, ValueError) as e:
        logging.error(f"修改 CSV 数据时出现错误: {str(e)}")
        raise  # 重新抛出异常，让上层调用者处理

    return csv_data
# 十一
def update_data2(csv_data, input_param, width, height, thick, force, tube_width, tube_thickness, weld, core_material, table):
    """通用的CSV数据更新函数"""
    try:
        # 获取列名
        header = csv_data[0]

        # 生成列名和索引的映射字典
        column_index_map = {col_name: header.index(col_name) for col_name in header}

        # 主视图，长度数量说明
        result_str = ''
        product_quantity = 0
        count = 0
        total_count = len(table)
        for index, (length, quantity) in enumerate(table):
            result_str += f'L={length}-{quantity}件, '
            product_quantity += quantity
            count += 1
            if count % 4 == 0 and index < total_count - 1:
                result_str += '\P'
        result_str = result_str.rstrip(' ， ')
        csv_data[75][column_index_map['值']] = f'\W0.7;\T1.1;{result_str}\P共计{product_quantity}件'

        # 端面
        update_cell_value(csv_data, 129, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 130, column_index_map, '覆盖值', width)
        update_cell_value(csv_data, 131, column_index_map, '覆盖值', height)
        update_cell_value(csv_data, 132, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 133, column_index_map, '覆盖值', tube_width)
        update_cell_value(csv_data, 134, column_index_map, '覆盖值', tube_width)

        # 方管厚度
        update_cell_value(csv_data, 104, column_index_map, '覆盖值', tube_thickness)

        # 端面焊缝
        update_cell_value(csv_data, 103, column_index_map, '值', f'\T1.1;{format_number(weld)}')

        # 耗能面设置
       
        update_cell_value(csv_data, 157, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 158, column_index_map, '覆盖值', height)

        # 连接板尺寸
        update_cell_value(csv_data, 170, column_index_map, '覆盖值', (width - thick) / 2)

        # 连接板数量
        update_cell_value(csv_data, 168, column_index_map, '值', f'\W0.7;\T1.1;连接板 H={format_number(thick)}-{format_number(product_quantity * 4)}件')

        # 挡板尺寸
        update_cell_value(csv_data, 181, column_index_map, '覆盖值', width + 5)
        update_cell_value(csv_data, 182, column_index_map, '覆盖值', thick + 5)
        update_cell_value(csv_data, 185, column_index_map, '覆盖值', thick + 5)
        update_cell_value(csv_data, 186, column_index_map, '覆盖值', height + 5)
        update_cell_value(csv_data, 175, column_index_map, '覆盖值', tube_width + 20 if tube_width != 200 else tube_width + 15)
        update_cell_value(csv_data, 178, column_index_map, '覆盖值', tube_width + 20 if tube_width != 200 else tube_width + 15)

        # 挡板焊缝
        update_cell_value(csv_data, 200, column_index_map, '值', f'\T1.1;C{format_number(weld)}')
        # 挡板数量
        update_cell_value(csv_data, 176, column_index_map, '值', f'\W0.7;\T1.1;挡板H=6-{format_number(product_quantity * 2)}件')


        # 标题栏，项目名称
        cell_with = 540 # 单元格宽度
        max_width = cell_with-20 # 字符串最大限制宽度
        dynamic_multiplier, true_length = calculate_dynamic_width(input_param, max_width) # 对项目名称字符串进行缩放，并返回倍率和实际宽度
        update_cell_value(csv_data, 247, column_index_map, '值', f'\W{dynamic_multiplier:.2f};\T1.1;{input_param}') # 更新值单元格值
        # 标题栏，项目名称，位置置中
        update_cell_value(csv_data, 247, column_index_map, '位置 X', - cell_with / 2 - true_length / 2) # 更新位置X单元格值

        # 标题栏，产品型号
        update_cell_value(csv_data, 249, column_index_map, '值', f'\W0.7;\T1.1;YSX-BRB-{force}-L')

        # 芯板材料
        update_cell_value(csv_data, 252, column_index_map, '值', f'芯板材料：{core_material}')
        

    except (IndexError, ValueError) as e:
        logging.error(f"修改 CSV 数据时出现错误: {str(e)}")
        raise  # 重新抛出异常，让上层调用者处理

    return csv_data
# 王一
def update_data3(csv_data, input_param, width, height, thick, force, tube_width, tube_thickness, weld, core_material, table):
    """通用的CSV数据更新函数"""
    try:
        # 获取列名
        header = csv_data[0]

        # 生成列名和索引的映射字典
        column_index_map = {col_name: header.index(col_name) for col_name in header}

        # 主视图，长度数量说明
        result_str = ''
        product_quantity = 0
        count = 0
        total_count = len(table)
        for index, (length, quantity) in enumerate(table):
            result_str += f'L={length}-{quantity}件, '
            product_quantity += quantity
            count += 1
            if count % 4 == 0 and index < total_count - 1:
                result_str += '\P'
        result_str = result_str.rstrip(' ， ')
        csv_data[77][column_index_map['值']] = f'\W0.7;\T1.1;{result_str}\P共计{product_quantity}件'

        # 端面
        update_cell_value(csv_data, 155, column_index_map, '覆盖值', width)
        update_cell_value(csv_data, 156, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 157, column_index_map, '覆盖值', height - thick - thick)
        update_cell_value(csv_data, 158, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 159, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 160, column_index_map, '覆盖值', tube_width)
        update_cell_value(csv_data, 161, column_index_map, '覆盖值', tube_width)
        update_cell_value(csv_data, 162, column_index_map, '覆盖值', thick)

        # 方管厚度
        update_cell_value(csv_data, 125, column_index_map, '覆盖值', tube_thickness)

        # 端面焊缝
        update_cell_value(csv_data, 124, column_index_map, '值', f'\T1.1;{format_number(weld)}')

        # 耗能面设置
       
        update_cell_value(csv_data, 193, column_index_map, '覆盖值', thick)
        update_cell_value(csv_data, 194, column_index_map, '覆盖值', height-thick-thick)

        # 连接板1尺寸
        update_cell_value(csv_data, 309, column_index_map, '覆盖值', width)
        # 连接板1数量
        update_cell_value(csv_data, 307, column_index_map, '值', f'\W0.7;\T1.1;连接板 H={format_number(thick)}-{format_number(product_quantity * 4)}件')

        # 连接板2尺寸
        update_cell_value(csv_data, 206, column_index_map, '覆盖值', (width - thick) / 2)
        # 连接板2数量
        update_cell_value(csv_data, 204, column_index_map, '值', f'\W0.7;\T1.1;连接板2 H={format_number(thick)}-{format_number(product_quantity * 4)}件')

        # 挡板尺寸
        update_cell_value(csv_data, 221, column_index_map, '覆盖值', width + 5)
        update_cell_value(csv_data, 222, column_index_map, '覆盖值', thick + 5)
        update_cell_value(csv_data, 223, column_index_map, '覆盖值', thick + 5)
        update_cell_value(csv_data, 224, column_index_map, '覆盖值', thick + 5)
        update_cell_value(csv_data, 227, column_index_map, '覆盖值', thick + 5)
        update_cell_value(csv_data, 228, column_index_map, '覆盖值', height - thick - thick - 5)
        update_cell_value(csv_data, 211, column_index_map, '覆盖值', tube_width + 20 if tube_width != 200 else tube_width + 15)
        update_cell_value(csv_data, 214, column_index_map, '覆盖值', tube_width + 20 if tube_width != 200 else tube_width + 15)

        # 挡板焊缝
        update_cell_value(csv_data, 250, column_index_map, '值', f'\T1.1;C{format_number(weld)}')
        # 挡板数量
        update_cell_value(csv_data, 212, column_index_map, '值', f'\W0.7;\T1.1;挡板H=6-{format_number(product_quantity * 2)}件')

         # 标题栏，项目名称
        cell_with = 540 # 单元格宽度
        max_width = cell_with-20 # 字符串最大限制宽度
        dynamic_multiplier, true_length = calculate_dynamic_width(input_param, max_width) # 对项目名称字符串进行缩放，并返回倍率和实际宽度
        update_cell_value(csv_data, 297, column_index_map, '值', f'\W{dynamic_multiplier:.2f};\T1.1;{input_param}') # 更新值单元格值
        # 标题栏，项目名称，位置置中
        update_cell_value(csv_data, 297, column_index_map, '位置 X', - cell_with / 2 - true_length / 2) # 更新位置X单元格值

        # 标题栏，产品型号
        update_cell_value(csv_data, 299, column_index_map, '值', f'\W0.7;\T1.1;YSX-BRB-{force}-L')
        
        # 芯板材料
        update_cell_value(csv_data, 310, column_index_map, '值', f'芯板材料：{core_material}')

    except (IndexError, ValueError) as e:
        logging.error(f"修改 CSV 数据时出现错误: {str(e)}")
        raise  # 重新抛出异常，让上层调用者处理

    return csv_data

# 预加载模板配置，避免每次循环都重新创建
# 使用绝对路径确保模板文件能正确找到
current_dir = os.path.dirname(os.path.abspath(__file__))
template_configs = {
    '王工': {
        'csv_file': os.path.join(current_dir, 'data', '王工.csv'),
        'update_function': update_data1
    },
    '十一': {
        'csv_file': os.path.join(current_dir, 'data', '十一.csv'),
        'update_function': update_data2
    },
    '王一': {
        'csv_file': os.path.join(current_dir, 'data', '王一.csv'),
        'update_function': update_data3
    }
}

"""处理参数"""
def brb_drawing(data_table, project_folder=None):
    # 确保数据表格是列表类型
    if not isinstance(data_table, list):
        data_table = [data_table]

    generated_files = []
    for row in data_table:
        try:
            logging.info(f"开始处理数据行: {row}")
            # 确保row是字典类型
            if not isinstance(row, dict):
                logging.error(f"数据行不是字典类型: {row}")
                continue
            
            # 从数据行中获取各参数值，使用get方法并设置默认值
            parameters = {
                "template": row.get("template"),  # 模版类型
                "project_name": row.get("project_name", ""),  # 项目名称
                "width": row.get("width"),  # 截面宽度
                "height": row.get("height"),  # 截面高度
                "thickness": row.get("thickness"),  # 板厚
                "force": row.get("force") or row.get("design_force"),  # 力 - 同时支持force和design_force字段
                "tube_width": row.get("tube_width"),  # 方管宽度
                "tube_thickness": row.get("tube_thickness"),  # 方管厚度
                "weld": row.get("weld"),  # 焊缝
                "core_material": row.get("core_material", "Q235"),  # 芯板材料，默认值Q235
                "table": row.get("length_quantity", [])  # 长度-数量表格
            }
            logging.info(f"解析参数: {parameters}")

            # 验证必要参数是否存在
            if not validate_required_parameters(parameters):
                continue

            # 转换数值类型
            parameters = convert_to_numeric(parameters)
            if parameters is None:
                continue

            # 直接使用预加载的模板配置
            config = template_configs.get(parameters["template"])
            
            # 如果找不到模板配置，直接报错
            if config is None:
                error_msg = f"未知的模板类型: {parameters['template']}，可用模板: {list(template_configs.keys())}"
                logging.error(error_msg)
                raise ValueError(error_msg)

            # 处理并生成图纸
            file_path = process_and_generate_drawing(parameters, config, project_folder)
            if file_path:
                generated_files.append(file_path)

        except Exception as e:
            logging.error(f"处理数据行时出错: {str(e)}")
    return generated_files

"""验证必要参数是否存在"""
def validate_required_parameters(params):
    # 确保params是字典类型
    if not isinstance(params, dict):
        logging.error(f"参数不是字典类型: {params}")
        return False
        
    required_params = ["template", "project_name", "width", "height", "thickness", "force", "tube_width", "tube_thickness", "weld"]
    missing_params = []

    for param in required_params:
        if param not in params or params[param] is None:
            missing_params.append(param)

    if missing_params:
        logging.warning(f"缺少必要参数: {', '.join(missing_params)}")
        return False
    return True

"""将参数转换为数值类型"""
def convert_to_numeric(params):
    # 确保params是字典类型
    if not isinstance(params, dict):
        logging.error(f"参数不是字典类型: {params}")
        return None
        
    numeric_params = ["width", "height", "thickness", "force", "tube_width", "tube_thickness", "weld"]
    for param in numeric_params:
        try:
            params[param] = int(params[param])
        except ValueError:
            logging.warning(f"'{param}' 必须为有效整数（如 123 ）！")
            return None
    return params

"""生成图纸"""
def process_and_generate_drawing(params, config, project_folder=None):
    try:
        logging.info(f"开始处理图纸生成，参数: {params}")
        logging.info(f"使用CSV模板文件: {config['csv_file']}")
        # 读取CSV文件
        with open(config['csv_file'], 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            csv_data = list(csv_reader)
        logging.info(f"成功读取CSV模板文件，共 {len(csv_data)} 行")

        # 输入参数并更新数据
        logging.info(f"调用更新函数: {config['update_function'].__name__}")
        csv_data = config['update_function'](csv_data, params["project_name"], params["width"],
                                             params["height"], params["thickness"], params["force"],
                                             params["tube_width"], params["tube_thickness"], params["weld"], params["core_material"], params["table"])
        logging.info("成功更新CSV数据")

        # 将修改后的数据写回到 CSV 文件
        with open(config['csv_file'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(csv_data)
        logging.info(f"成功将修改后的数据写回到CSV文件: {config['csv_file']}")

        # 直接保存到项目文件夹，不弹出选择对话框
        default_filename = f'{params["project_name"]} BRB-{format_number(params["force"])}-L 方管宽{format_number(params["tube_width"])}.dxf'
        
        # 生成DXF文件
        if project_folder:
            # 如果提供了项目文件夹，将文件保存在该目录下的以项目名称命名的子文件夹中
            save_dir = os.path.join(project_folder, params["project_name"])
            
            # 确保保存目录存在
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
                
            # 构建完整的保存路径
            output_dxf_file = os.path.join(save_dir, default_filename)
            # 执行保存操作
            csv_to_dxf(config['csv_file'], output_dxf_file)
            logging.info(f"图纸生成成功并保存到磁盘: {output_dxf_file}")
            return output_dxf_file
        else:
            # 如果没有提供项目文件夹，生成临时文件
            import tempfile
            import io
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as temp_file:
                temp_dxf_path = temp_file.name
            
            # 执行保存操作到临时文件
            csv_to_dxf(config['csv_file'], temp_dxf_path)
            
            # 读取临时文件内容到内存流
            output = io.BytesIO()
            with open(temp_dxf_path, 'rb') as f:
                output.write(f.read())
            output.seek(0)
            
            # 删除临时文件
            os.remove(temp_dxf_path)
            
            logging.info("图纸生成成功并返回内存流")
            return (output, default_filename)

    except FileNotFoundError:
        logging.error(f"文件不存在: {config['csv_file']}")
        return None
    except Exception as e:
        logging.error(f"处理文件时出错: {str(e)}")
        return None
    
    return None


"""格式化数字，去除多余的零和小数点"""
def format_number(num):   
    formatted = "{:.3f}".format(num).rstrip('0').rstrip('.') if isinstance(num, (int, float)) else str(num)
    return formatted


"""安全地更新单元格值"""
def update_cell_value(csv_data, row_index, column_map, column_name, value):
    if row_index < len(csv_data) and column_name in column_map:
        csv_data[row_index][column_map[column_name]] = format_number(value)
    else:
        logging.warning(f"无法更新单元格: 行索引 {row_index} 或列名 {column_name} 不存在")

# 限制字符总长，并返回比例和总宽度
def calculate_dynamic_width(text, max_width=300, base_width_cn=60):

    base_width_en = base_width_cn/2

    # 计算不同类型字符的数量
    cn_count = 0  # 中文字符数量
    en_count = 0  # 英文字符数量（包括数字和符号）

    for char in text:
        # 判断是否为中文字符（Unicode范围：0x4E00-0x9FFF）
        if 0x4E00 <= ord(char) <= 0x9FFF:
            cn_count += 1
        else:
            en_count += 1

    # 计算总字符数量
    total_count = cn_count + en_count

    # 估算1倍率下的总宽度
    estimated_total_length = (cn_count * base_width_cn) + (en_count * base_width_en)

    # 计算动态宽度倍率
    if total_count > 0 and estimated_total_length > 0:
        dynamic_multiplier = max_width / estimated_total_length
        # 限制倍率范围
        dynamic_multiplier = max(0.3, min(dynamic_multiplier, 0.8))
    else:
        dynamic_multiplier = 0.8  # 默认倍率

    true_length = (cn_count * base_width_cn * dynamic_multiplier) + (en_count * base_width_en * dynamic_multiplier)

    # 返回动态倍率和实际宽度
    return dynamic_multiplier, true_length

# 测试
if __name__ == "__main__":
    # 新增：设置工作目录为当前文件所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    """
        根据数据表格生成图纸
    """

    data_table = [{
        "template": "王工",
        "core_material": "Q345",  # 芯板材料
        "project_name": "等等的点点滴滴项目名称",
        "width": 160,  # 截面宽度
        "height": 160,  # 截面高度
        "thickness": 12,  # 板厚
        "force": 2000,  # 力
        "tube_width": 250,  # 方管宽度
        "tube_thickness": 6,  # 方管厚度
        "weld": 10,  # 焊缝
        "length_quantity": [(5000, 2), (6000, 3)]  # 添加长度-数量表格
    }]

    # 调用函数
    brb_drawing(data_table)