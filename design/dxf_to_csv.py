import ezdxf
import csv
import logging
import math

# 配置日志记录
logging.basicConfig(filename='dxf_csv_conversion.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# 定义尺寸标注类型映射
DIMTYPE_MAPPING = {
    0: "UNKNOWN",
    1: "LINEAR",
    2: "ALIGNED",
    3: "ANGULAR",
    4: "DIAMETER",
    5: "RADIUS",
    6: "ANGULAR_3P",
    7: "ORDINATE",
    8: "LINEAR_HORIZONTAL",
    9: "LINEAR_VERTICAL",
    10: "LINEAR_ROTATED",
    32: "LINEAR",
    160: "LINEAR",
    163: "DIAMETER",
    35: "DIAMETER",
    164: "RADIUS",
    36: "RADIUS",
    34: "ANGULAR"
}

# 手动定义一些常见线型的图案信息（仅作为自动获取失败时的回退选项）
COMMON_LINETYPE_PATTERNS = {
    "点画线": [18*9, 12*9, 2*9, 2*9, 2*9],  # 仅在自动获取失败时使用
    "虚线": [2.0*9, 1.0*9, 1.0*9]  # 仅在自动获取失败时使用
}

# 数字格式化，保留三位小数，去除末尾0
def format_number(num):
    formatted = "{:.3f}".format(num).rstrip('0').rstrip('.') if isinstance(num, (int, float)) else str(num)
    return formatted

# 获取线型函数

def get_linetype_pattern(doc, linetype):
    linetype_obj = doc.linetypes.get(linetype)
    pattern = []
    if linetype_obj:
        try:
            # 使用ezdxf提供的simplified_line_pattern方法获取线型图案
            if hasattr(linetype_obj, 'simplified_line_pattern'):
                pattern = linetype_obj.simplified_line_pattern()
                logging.info(f"使用simplified_line_pattern()获取到的线型图案: {pattern}")
            
            # 如果获取到的pattern是None或空列表，尝试其他方式
            if not pattern:
                # 尝试多种可能的属性名获取线型图案
                if hasattr(linetype_obj.dxf, 'dash_lengths'):
                    pattern = linetype_obj.dxf.dash_lengths
                elif hasattr(linetype_obj, 'pattern'):
                    pattern = linetype_obj.pattern
                elif hasattr(linetype_obj.dxf, 'pattern'):
                    pattern = linetype_obj.dxf.pattern
                elif hasattr(linetype_obj, 'dash_lengths'):
                    pattern = linetype_obj.dash_lengths
            
        except Exception as e:
            logging.warning(f"获取线型 {linetype} 的图案信息时发生错误: {str(e)}")
            # 仅在无法自动获取时才使用手动定义的图案
            if linetype in COMMON_LINETYPE_PATTERNS:
                pattern = COMMON_LINETYPE_PATTERNS[linetype]
                logging.info(f"使用手动定义的图案信息: {pattern}")
    
    if linetype == "Continuous" or "continuous" in linetype.lower():
        pattern = []
        
    return pattern

# 获取图层信息函数
def write_layer_info(doc, writer):
    for layer in doc.layers:
        linetype = layer.dxf.linetype
        pattern = get_linetype_pattern(doc, linetype)
        linetype_obj = doc.linetypes.get(linetype)
        description = linetype_obj.dxf.description if linetype_obj else ""
        row = {
            "实体类型": "图层",
            "图层": layer.dxf.name,
            "颜色": layer.dxf.color,
            "线型": linetype,
            "线宽": layer.dxf.lineweight,
            "线型描述": description,
            "线型图案": ";".join(map(str, pattern)),
        }
        writer.writerow(row)

# 直线
def process_line(entity, row):
    try:
        start = entity.dxf.start
        end = entity.dxf.end
        row.update({
            '起点 X': format_number(start[0]),
            '起点 Y': format_number(start[1]),
            '终点 X': format_number(end[0]),
            '终点 Y': format_number(end[1])
        })
    except AttributeError:
        logging.warning(f"LINE 实体缺少必要属性，跳过此实体")

# 圆
def process_circle(entity, row):
    try:
        center = entity.dxf.center
        radius = entity.dxf.radius
        row.update({
            '圆心 X': format_number(center[0]),
            '圆心 Y': format_number(center[1]),
            '半径': format_number(radius)
        })
    except AttributeError:
        logging.warning(f"CIRCLE 实体缺少必要属性，跳过此实体")

# 圆弧
def process_arc(entity, row):
    try:
        center = entity.dxf.center
        radius = entity.dxf.radius
        start_angle = entity.dxf.start_angle
        end_angle = entity.dxf.end_angle
        row.update({
            '圆心 X': format_number(center[0]),
            '圆心 Y': format_number(center[1]),
            '半径': format_number(radius),
            '起始角度': format_number(start_angle),
            '终止角度': format_number(end_angle)
        })
    except AttributeError:
        logging.warning(f"ARC 实体缺少必要属性，跳过此实体")

# 多段线
def process_lwpolyline(entity, row):
    try:
        vertices = []
        if entity.closed:
            closed = "是"
        else:
            closed = "否"
        for vertex in entity.get_points(format='xyseb'):
            x, y, start_width, end_width, bulge = vertex
            vertices.append(f"({format_number(x)}, {format_number(y)}, {format_number(start_width)}, {format_number(end_width)}, {format_number(bulge)})")
        vertex_data = "; ".join(vertices)
        row.update({
            '顶点数据': vertex_data,
            '闭合': closed
        })
    except AttributeError:
        logging.warning(f"LWPOLYLINE 实体缺少必要属性，跳过此实体")

# 尺寸
def process_dimension(entity, row):
    try:
        #获取尺寸编码,尺寸类型,尺寸值
        dim_code = entity.dxf.dimtype
        dim_value = entity.get_measurement()
        # 获取尺寸样式名称
        dimstyle_name = entity.dxf.dimstyle
        row.update({
            '尺寸编码': str(dim_code),
            '类型/名称': DIMTYPE_MAPPING.get(dim_code, "UNKNOWN"),
            '值': format_number(dim_value),
            '尺寸样式': dimstyle_name
        })
        # 处理线型尺寸
        if row["类型/名称"] in ["LINEAR", "ALIGNED", "LINEAR_HORIZONTAL", "LINEAR_VERTICAL", "LINEAR_ROTATED"]:
            # 获取尺寸位置
            location = entity.dxf.defpoint
            # 获取尺寸起点和终点
            dim_start = entity.dxf.defpoint2
            dim_end = entity.dxf.defpoint3
            if entity.dxf.text:
                dim_text = entity.dxf.text
            else:
                dim_text = "<>"
            row.update({
                '位置 X': format_number(location[0]),
                '位置 Y': format_number(location[1]),
                '起点 X': format_number(dim_start[0]),
                '起点 Y': format_number(dim_start[1]),
                '终点 X': format_number(dim_end[0]),
                '终点 Y': format_number(dim_end[1]),
                '角度': format_number(entity.dxf.angle),
                '覆盖值': dim_text
            })
        # 处理直径尺寸
        elif row["类型/名称"] == "DIAMETER":
            # 直径中，defpoint为尺寸起点，defpoint4为尺寸终点
            dim_start = entity.dxf.defpoint
            dim_end = entity.dxf.defpoint4
            # 计算圆心
            center_x = (dim_start[0] + dim_end[0]) / 2
            center_y = (dim_start[1] + dim_end[1]) / 2
            # 计算角度
            dx = dim_end[0] - dim_start[0]
            dy = dim_end[1] - dim_start[1]
            angle = math.degrees(math.atan2(dy, dx))
            # 获取文本位置
            text_position = entity.dxf.text_midpoint
            # 获取文本内容
            if entity.dxf.text:
                dim_text = entity.dxf.text
            else:
                dim_text = "<>"
            row.update({
                '圆心 X': format_number(center_x),
                '圆心 Y': format_number(center_y),
                '角度': format_number(angle),
                '位置 X': format_number(text_position[0]),
                '位置 Y': format_number(text_position[1]),
                '覆盖值': dim_text
            })
        # 获取半径尺寸
        elif row["类型/名称"] == "RADIUS":
            # 半径尺寸，defpoint为起点，就是圆心
            dim_start = entity.dxf.defpoint
            dim_end = entity.dxf.defpoint4
            center_x = dim_start[0]
            center_y = dim_start[1]
            # 计算角度
            dx = dim_end[0] - dim_start[0]
            dy = dim_end[1] - dim_start[1]
            angle = math.degrees(math.atan2(dy, dx))
            # 获取文本位置
            text_position = entity.dxf.text_midpoint

            row.update({
                '圆心 X': format_number(center_x),
                '圆心 Y': format_number(center_y),
                '角度': format_number(angle),
                '位置 X': format_number(text_position[0]),
                '位置 Y': format_number(text_position[1])
            })
        # 获取角度尺寸(无法成功获取数据，停用)
        '''elif row["类型/名称"] == "ANGULAR":
            # 获取角度值
            angle_value = entity.dxf.angle
            print(1)
            # 获取尺寸标注的位置
            dim_position = entity.base
            print(dim_position)
            # 获取尺寸标注的文本内容
            dim_text = entity.text
            # 获取点位
            p1 = entity.get_dxf_attrib('defpoint2', print("none"))
            p2 = entity.dxf.defpoint2
            p3 = entity.dxf.defpoint3
            print(p1)
            row.append({
                '角度': angle_value,
                '位置 X': format_number(dim_position[0]),
                '位置 Y': format_number(dim_position[1]),
                '值': dim_text
            })
            print(row["类型/名称"])'''
        if row["类型/名称"] == "UNKNOWN":
            logging.warning(f"发现未知尺寸类型，尺寸编码为 {dim_code}，实体句柄为 {entity.dxf.handle}")
            print(f"发现未知尺寸类型，尺寸编码为 {dim_code}，实体句柄为 {entity.dxf.handle}")
    except AttributeError:
        logging.warning(f"DIMENSION 实体缺少必要属性，跳过此实体")

# 写入dimstyle定义函数
def write_dimstyle_info(doc, writer):
    for dimstyle in doc.dimstyles:
        dimstyle_name = str(dimstyle.dxf.name)
        if dimstyle:
            try:
                # 收集dimstyle属性
                dim_attribs = {
                    'dimtxt': dimstyle.dxf.dimtxt,
                    'dimclrd': dimstyle.dxf.dimclrd,
                    'dimasz': dimstyle.dxf.dimasz,
                    'dimtad': dimstyle.dxf.dimtad,
                    'dimjust': dimstyle.dxf.dimjust,
                    'dimlwd': dimstyle.dxf.dimlwd,
                    'dimexo': dimstyle.dxf.dimexo,
                    'dimscale': dimstyle.dxf.dimscale,
                    'dimalt': dimstyle.dxf.dimalt,
                    'dimadec': dimstyle.dxf.dimadec,
                    'dimdsep': dimstyle.dxf.dimdsep
                }
                # 将属性转换为JSON字符串
                import json
                dim_attribs_str = json.dumps(dim_attribs)
                
                row = {
                    "实体类型": "dimstyle",
                    "类型/名称": dimstyle_name,
                    "值": dim_attribs_str
                }
                writer.writerow(row)
            except Exception as e:
                import logging
                logging.warning(f"处理dimstyle '{dimstyle_name}' 时发生错误: {str(e)}")


# 文本

def process_text(entity, row):
    try:
        if entity.dxftype() == 'TEXT':
            text_content = entity.dxf.text
            text_location = entity.dxf.insert
            text_height = entity.dxf.height
            text_rotation = entity.dxf.rotation
        else:  # MTEXT
            text_content = entity.text
            text_location = entity.dxf.insert
            text_height = entity.dxf.char_height
            text_rotation = entity.dxf.rotation
        row.update({
            '值': text_content,
            '位置 X': format_number(text_location[0]),
            '位置 Y': format_number(text_location[1]),
            '高度': format_number(text_height),
            '角度': format_number(text_rotation)
        })
    except AttributeError:
        logging.warning(f"TEXT 实体缺少必要属性，跳过此实体")

# 剖面线
def process_hatch(entity, row):
    try:
        pattern_name = entity.dxf.pattern_name
        boundary_vertices = []
        for path in entity.paths:
            if hasattr(path, 'vertices'):
                for vertex in path.vertices:
                    boundary_vertices.append(f"({format_number(vertex[0])}, {format_number(vertex[1])}, {format_number(vertex[2])})")
            elif hasattr(path, 'edges'):
                for edge in path.edges:
                    if hasattr(edge, 'start') and hasattr(edge, 'end'):
                        start_x, start_y = edge.start
                        end_x, end_y = edge.end
                        boundary_vertices.append(f"({format_number(start_x)}, {format_number(start_y)})")
                        boundary_vertices.append(f"({format_number(end_x)}, {format_number(end_y)})")
                    elif hasattr(edge, 'center') and hasattr(edge, 'radius') and hasattr(edge, 'start_angle') and hasattr(
                            edge, 'end_angle'):
                        center = edge.center
                        radius = edge.radius
                        start_angle = edge.start_angle
                        end_angle = edge.end_angle
                        start_x = center[0] + radius * math.cos(math.radians(start_angle))
                        start_y = center[1] + radius * math.sin(math.radians(start_angle))
                        end_x = center[0] + radius * math.cos(math.radians(end_angle))
                        end_y = center[1] + radius * math.sin(math.radians(end_angle))
                        # 根据圆弧的起止角度计算凸起值
                        delta_angle = math.radians(end_angle - start_angle)
                        bulge = math.tan(delta_angle / 4)
                        boundary_vertices.append(f"({format_number(start_x)}, {format_number(start_y)}, {format_number(bulge)}")
                        boundary_vertices.append(f"({format_number(end_x)}, {format_number(end_y)})")
        row.update({
            '类型/名称': pattern_name,
            '顶点数据': "; ".join(boundary_vertices)
        })
        try:
            scale = entity.dxf.pattern_scale
            row.update({
                '缩放比例': format_number(scale)
            })
        except AttributeError:
            row.update({
                '缩放比例': "未知"
            })
            logging.warning(f"无法获取 HATCH 实体 {entity.dxf.handle} 的填充缩放比例，将使用 '未知' 代替。")
    except AttributeError:
        logging.warning(f"HATCH 实体缺少必要属性，跳过此实体")

# 块
def process_insert(entity, row, writer):
    insert_location = entity.dxf.insert
    row.update({
        '块名': f"块名: {entity.dxf.name}",
        '位置 X': format_number(insert_location[0]),
        '位置 Y': format_number(insert_location[1]),
    })
    writer.writerow(row)

    block_def = entity.block()  # 调用 block 方法获取块定义对象
    for nested_entity in block_def:
        nested_row = {
            '实体类型': nested_entity.dxftype(),
            '图层': nested_entity.dxf.layer,
            '颜色': nested_entity.dxf.color,
            '线型': nested_entity.dxf.linetype,
            '线宽': nested_entity.dxf.lineweight,
            '块名': f"引用于: {entity.dxf.name}"
        }
        if nested_entity.dxftype() == 'LINE':
            process_line(nested_entity, nested_row)
        elif nested_entity.dxftype() == 'CIRCLE':
            process_circle(nested_entity, nested_row)
        elif nested_entity.dxftype() == 'LWPOLYLINE':
            process_lwpolyline(nested_entity, nested_row)
        elif nested_entity.dxftype() == 'DIMENSION':
            process_dimension(nested_entity, nested_row)
        elif nested_entity.dxftype() == 'ARC':
            process_arc(nested_entity, nested_row)
        elif nested_entity.dxftype() in ['TEXT', 'MTEXT']:
            process_text(nested_entity, nested_row)
        elif nested_entity.dxftype() == 'HATCH':
            process_hatch(nested_entity, nested_row)
        elif nested_entity.dxftype() == 'INSERT':
            process_insert(nested_entity, nested_row, writer)
        writer.writerow(nested_row)

# dxf转csv主函数
def dxf_to_csv(input_file, output_file):
    print(f"开始转换: {input_file} -> {output_file}")
    try:
        doc = ezdxf.readfile(input_file)
        msp = doc.modelspace()
        print(f"成功打开DXF文件，模型空间有 {len(msp)} 个实体")
        fieldnames = [
            '实体类型', '图层', '颜色', '线型', '线宽', '线型描述', '线型图案',
            '类型/名称', '块名', '值', '覆盖值', '位置 X', '位置 Y', '起点 X', '起点 Y', '终点 X', '终点 Y',
            '圆心 X', '圆心 Y', '半径', '顶点数据', '闭合', '高度', '角度', '尺寸编码',
            '起始角度', '终止角度', '缩放比例', '尺寸样式'
        ]
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            # 写入图层信息
            write_layer_info(doc, writer)

            for entity in msp:
                row = {
                    '实体类型': entity.dxftype(),
                    '图层': entity.dxf.layer,
                    '颜色': entity.dxf.color,
                    '线型': entity.dxf.linetype,
                    '线宽': entity.dxf.lineweight,
                }
                if entity.dxftype() == 'LINE':
                    process_line(entity, row)
                    writer.writerow(row)
                elif entity.dxftype() == 'CIRCLE':
                    process_circle(entity, row)
                    writer.writerow(row)
                elif entity.dxftype() == 'LWPOLYLINE':
                    process_lwpolyline(entity, row)
                    writer.writerow(row)
                elif entity.dxftype() == 'DIMENSION':
                    process_dimension(entity, row)
                    writer.writerow(row)
                elif entity.dxftype() == 'ARC':
                    process_arc(entity, row)
                    writer.writerow(row)
                elif entity.dxftype() in ['TEXT', 'MTEXT']:
                    process_text(entity, row)
                    writer.writerow(row)
                elif entity.dxftype() == 'HATCH':
                    process_hatch(entity, row)
                    writer.writerow(row)
                elif entity.dxftype() == 'INSERT':
                    process_insert(entity, row, writer)

            # 写入dimstyle信息
            write_dimstyle_info(doc, writer)


        logging.info(f"{input_file} 已成功转换为 {output_file} (DXF to CSV)")
        return output_file
    except IOError:
        logging.error(f"文件 {input_file} 未找到或不是有效的 DXF 文件")
        return None
    except ezdxf.DXFStructureError:
        logging.error(f"文件 {input_file} 是无效或损坏的 DXF 文件")
        return None
    except Exception as e:
        logging.error(f"转换过程中发生错误: {str(e)}")
        return None