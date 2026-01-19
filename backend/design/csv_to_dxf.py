import ezdxf
import csv
import logging

# 配置日志记录
logging.basicConfig(filename='dxf_csv_conversion.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# 全局缩放因子，默认为5
global_scale_factor = 5

# 定义BYLAYER默认颜色
def handle_color(color):
    if color == 'BYLAYER':
        return 256
    try:
        return int(color) if color is not None else 256
    except (ValueError, TypeError):
        return 256

# 安全转换数值函数
def safe_float(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

# csv转dxf主函数，创建新的DXF文档
def csv_to_dxf(input_file, output_file):
    try:
        # 创建一个新的 DXF 文档
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        drawing(doc, msp, input_file, output_file)
        return output_file
    except FileNotFoundError:
        logging.error(f"文件 {input_file} 未找到")
        return None
    except Exception as e:
        logging.error(f"发生未知错误: {str(e)}")
        return None


# csv转dxf主函数，添加到已有的DXF文档
def csv_add_dxf(input_file, output_file):
    try:
        # 打开一个 DXF 文档
        doc = ezdxf.readfile(output_file)
        msp = doc.modelspace()
        drawing(doc, msp, input_file, output_file)

    except FileNotFoundError:
        logging.error(f"文件 {input_file} 未找到")
    except Exception as e:
        logging.error(f"发生未知错误: {str(e)}")

# 绘制函数，用于绘制实体到DXF文档，根据输入文件类型选择不同的绘制方法
def drawing(doc, msp, input_file, output_file):
    global global_scale_factor  # 声明使用全局变量
    layer_dict = {}
    dimstyles_dict = {}  # 存储所有dimstyle
    scale_factor = global_scale_factor  # 初始化缩放比例为全局默认值

    with open(input_file, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        data = list(reader)

    # 第一次遍历整个csv表格，仅处理 dimstyle 与图层信息
    dimstyle_name = ""  # 用于存储默认dimstyle名称
    for line_num, row in enumerate(data, start=2):  # 从第 2 行开始计数
        line_num -= 1
        # 调试：检查row的数据类型
        print(f"Row type at line {line_num}: {type(row)}")
        print(f"Row content: {row}")
        if not isinstance(row, dict):
            print(f"ERROR: Row at line {line_num} is not a dict!")
       
        # 首先读取图层信息
        if row["实体类型"] == "图层":
            layer = row["图层"]
            color = handle_color(row["颜色"])
            linetype = row["线型"]
            lineweight = int(row["线宽"])
            linetype_description = row["线型描述"]
            linetype_pattern_str = row["线型图案"]
            linetype_pattern = handle_linetype_pattern(linetype_pattern_str, linetype, input_file, layer)
            create_layer(doc, layer, color, linetype, lineweight, linetype_description, linetype_pattern,
                         input_file)
            layer_dict[layer] = (color, linetype, lineweight)

        # 处理标注样式
        if row["实体类型"] == "dimstyle":
            current_dimstyle_name = row["类型/名称"]
            # 解析dimstyle属性并替换scale_factor变量
            dim_attribs_str = row["值"]
            dim_attribs_str = dim_attribs_str.replace('scale_factor', str(scale_factor))
            current_dxf_attribs = eval(dim_attribs_str)
            # 将dimstyle存储到字典中
            dimstyles_dict[current_dimstyle_name] = current_dxf_attribs
            # 将最后一个遇到的dimstyle设置为默认dimstyle
            dimstyle_name = current_dimstyle_name
            dxf_attribs = current_dxf_attribs                         

    
    # 创建默认的dimstyle    
    if dimstyle_name == "":
        dimstyle_name = "CUSTOM_DIMSTYLE"
        dxf_attribs = {
                    "dimtxt": 3.5,  # 尺寸文本高度为3.5个绘图单位
                    "dimclrd": 3,  # 尺寸线和尺寸界线的颜色，值3通常代表绿色(根据CAD颜色索引表)
                    "dimasz": 3,  # 尺寸箭头大小为3个绘图单位
                    "dimtad": 1,  # 尺寸文本垂直位置：1=上方(相对于尺寸线)
                    "dimjust": 0,  # 尺寸文本水平对齐：0=左对齐
                    "dimlwd": 0.25,  # 尺寸线和尺寸界线的线宽为0.25个单位
                    "dimexo": 0,  # 尺寸界线超出尺寸线的长度为0
                    "dimscale": scale_factor,  # 使用获取的缩放比例
                    "dimalt": 0,  # 是否启用替代单位：0=不启用
                    "dimadec": 3,  # 尺寸标注的小数位数精度：保留3位小数
                    "dimdsep": ord('.'),  # 尺寸标注的小数分隔符：使用英文句号(ASCII码值46)
                    # 其他可选参数...
                }
    

    # 将默认dimstyle添加到字典中
    if dimstyle_name not in dimstyles_dict:
        dimstyles_dict[dimstyle_name] = dxf_attribs
    
    # 创建所有dimstyle
    for name, attribs in dimstyles_dict.items():
        # 检查dimstyle是否已存在
        if name not in doc.dimstyles:
            doc.dimstyles.new(name, dxfattribs=attribs)
        else:
            # 如果已存在，可以选择更新属性或跳过
            print(f"dimstyle '{name}' 已存在，将跳过创建")


    # 第二次遍历，处理实体
    for line_num, row in enumerate(data, start=2):
        line_num -= 1
        # 读取非块元素
        if not row["块名"]:
            try:
                entity_type = row["实体类型"]
                layer = row["图层"]
                color = handle_color(row["颜色"])
                linetype = row["线型"]
                try:
                    lineweight = int(row["线宽"]) if row["线宽"] else -1
                except (ValueError, TypeError):
                    lineweight = -1

                # 跳过dimstyle定义行
                if entity_type.lower() == 'dimstyle':
                    continue
                
                if entity_type == 'LINE':
                    handle_line(row, msp, layer, color, linetype, lineweight, input_file, line_num)
                elif entity_type == 'CIRCLE':
                    handle_circle(row, msp, layer, color, linetype, lineweight, input_file, line_num)
                elif entity_type == 'LWPOLYLINE':
                    handle_lwpolyline(row, msp, layer, color, linetype, lineweight, input_file, line_num)
                elif entity_type == 'DIMENSION':
                    handle_dimension(row, msp, layer, color, linetype, lineweight, input_file, line_num, dimstyle_name)
                elif entity_type == 'ARC':
                    handle_arc(row, msp, layer, color, linetype, lineweight, input_file, line_num)
                elif entity_type in ['TEXT', 'MTEXT']:
                    handle_text(row, msp, layer, color, input_file, entity_type, line_num)
                elif entity_type == 'HATCH':
                    handle_hatch(row, msp, layer, color, input_file, line_num)
            except Exception as e:
                messagebox.showwarning("警告", f"文件 {input_file} 第 {line_num} 行发生未知错误: {str(e)}，将略过此数据。")
                logging.warning(f"文件 {input_file} 第 {line_num} 行发生未知错误: {str(e)}，将略过此数据。")
        # 读取块元素
        elif row["实体类型"] == 'INSERT':
            try:
                layer = row["图层"]
                color = handle_color(row["颜色"])
                linetype = row["线型"]
                try:
                    lineweight = int(row["线宽"]) if row["线宽"] else -1
                except (ValueError, TypeError):
                    lineweight = -1
                handle_insert(data, row, msp, doc, layer, color, linetype, lineweight, input_file, dimstyle_name)

            except Exception as e:
                messagebox.showwarning("警告", f"文件 {input_file} 第 {line_num} 行发生未知错误: {str(e)}，将略过此数据。")
                logging.warning(f"文件 {input_file} 第 {line_num} 行发生未知错误: {str(e)}，将略过此数据。")

    # 保存 DXF 文件
    print(f"正在保存 DXF 文件: {output_file}")
    doc.saveas(output_file)
    print(f"DXF 文件已成功保存")
    logging.info(f"{input_file} 已成功转换为 {output_file} (CSV to DXF)")


# 设置线型函数
def handle_linetype_pattern(linetype_pattern_str, linetype, input_file, layer):
    linetype_pattern = []
    if linetype_pattern_str:
        parts = linetype_pattern_str.split(";")
        try:
            # 转换为浮点数
            pattern_values = [float(part.strip()) for part in parts]
            
            if pattern_values:
                # 计算所有值的绝对值之和作为总长度
                total_length = sum(abs(v) for v in pattern_values)
                
                # 根据用户需求：在图案前面添加总长度
                # 例如：108;18;18;18;0 -> [162.0, 108.0, 18.0, 18.0, 18.0, 0.0]
                linetype_pattern = [total_length] + pattern_values
                
        except ValueError:
            if linetype != "Continuous":
                logging.warning(
                    f"文件 {input_file} 中图层 {layer} 的线型图案字段 '{linetype_pattern_str}' 包含无效数据，将使用空列表代替。")
    return linetype_pattern


# 创建图层函数
def create_layer(doc, layer, color, linetype, lineweight, linetype_description, linetype_pattern, input_file):
    if layer not in doc.layers:
        try:
            if linetype not in doc.linetypes:
                if linetype_pattern:
                    # 保持原始线型图案，不强制要求偶数长度
                    doc.linetypes.add(
                        name=linetype,
                        pattern=linetype_pattern,
                        description=linetype_description
                    )
                elif linetype != "Continuous":
                    logging.warning(f"文件 {input_file} 中图层 '{layer}' 使用了未知线型 '{linetype}'，将使用默认实线。")
                    linetype = "CONTINUOUS"
            doc.layers.new(name=layer, dxfattribs={
                "color": color,
                "linetype": linetype,
                "lineweight": lineweight
            })
        except ezdxf.DXFValueError:
            logging.warning(f"文件 {input_file} 中图层 '{layer}' 无法创建，可能是无效的线型或线宽。将使用默认设置。")
            if layer not in doc.layers:
                doc.layers.new(name=layer)


# 绘制直线函数
def handle_line(row, msp, layer, color, linetype, lineweight, input_file, line_num):
    try:
        start = (float(row["起点 X"]), float(row["起点 Y"]))
        end = (float(row["终点 X"]), float(row["终点 Y"]))
        msp.add_line(start, end,
                     dxfattribs={"layer": layer, "color": color, "linetype": linetype, "lineweight": lineweight})
    except (ValueError, TypeError):
        messagebox.showwarning("警告",
                               f"文件 {input_file} 第 {line_num} 行的 LINE 实体坐标字段包含无效数据，将略过此数据。")
        logging.warning(f"文件 {input_file} 第 {line_num} 行的 LINE 实体坐标字段包含无效数据，将略过此数据。")


# 绘制圆形函数
def handle_circle(row, msp, layer, color, linetype, lineweight, input_file, line_num):
    try:
        center = (float(row["圆心 X"]), float(row["圆心 Y"]))
        radius = float(row["半径"])
        msp.add_circle(center, radius,
                       dxfattribs={"layer": layer, "color": color, "linetype": linetype, "lineweight": lineweight})
    except (ValueError, TypeError):
        messagebox.showwarning("警告",
                               f"文件 {input_file} 第 {line_num} 行的 CIRCLE 实体坐标或半径字段包含无效数据，将略过此数据。")
        logging.warning(f"文件 {input_file} 第 {line_num} 行的 CIRCLE 实体坐标或半径字段包含无效数据，将略过此数据。")


# 绘制多段线函数
def handle_lwpolyline(row, msp, layer, color, linetype, lineweight, input_file, line_num):
    vertices = []
    points = row["顶点数据"].split("; ")
    if row["闭合"] == "是":
        closed = True
    else:
        closed = False
    for point in points:
        try:
            x, y, start_width, end_width, bulge = point.strip("()").split(", ")
            vertices.append(
                (float(x), float(y), float(start_width), float(end_width), float(bulge)))
        except ValueError:
            messagebox.showwarning("警告",
                                   f"文件 {input_file} 第 {line_num} 行的 LWPOLYLINE 实体顶点数据包含无效数据，将略过此数据。")
            logging.warning(
                f"文件 {input_file} 第 {line_num} 行的 LWPOLYLINE 实体顶点数据包含无效数据，将略过此数据。")
            vertices = []
            break
    if vertices:
        msp.add_lwpolyline(vertices,
                           dxfattribs={"layer": layer, "color": color, "linetype": linetype, "lineweight": lineweight,
                                       "closed": closed})


# 绘制尺寸函数
def handle_dimension(row, msp, layer, color, linetype, lineweight, input_file, line_num, dimstyle_name="CUSTOM_DIMSTYLE"):
    dim_type = row["类型/名称"]
    dim_code = row["尺寸编码"]

    # 优先使用CSV中保存的尺寸样式
    entity_dimstyle = row.get("尺寸样式", "")
    if entity_dimstyle:
        dimstyle_name = entity_dimstyle

    dim_angle = safe_float(row["角度"])
    if dim_type == "UNKNOWN":
        messagebox.showwarning("警告", f"第 {line_num} 行的尺寸标注类型未知，尺寸编码为 {dim_code}，将略过此尺寸。")
        logging.warning(f"第 {line_num} 行的尺寸标注类型未知，尺寸编码为 {dim_code}，将略过此尺寸。")
        return
    if dim_type in ["LINEAR", "ALIGNED", "LINEAR_HORIZONTAL", "LINEAR_VERTICAL", "LINEAR_ROTATED"]:
        try:
            location = (float(row["位置 X"]), float(row["位置 Y"]))

            # 通过调整尺寸初始点和角度，来调整尺寸显示位置。
            if 90 <= dim_angle <= 120 or 270 <= dim_angle <= 300:
                if float(row["终点 Y"]) > float(row["起点 Y"]):
                    p1 = (float(row["起点 X"]), float(row["起点 Y"]))
                    p2 = (float(row["终点 X"]), float(row["终点 Y"]))
                else:
                    p2 = (float(row["起点 X"]), float(row["起点 Y"]))
                    p1 = (float(row["终点 X"]), float(row["终点 Y"]))
            elif float(row["终点 X"]) > float(row["起点 X"]):
                p1 = (float(row["起点 X"]), float(row["起点 Y"]))
                p2 = (float(row["终点 X"]), float(row["终点 Y"]))
            else:
                p2 = (float(row["起点 X"]), float(row["起点 Y"]))
                p1 = (float(row["终点 X"]), float(row["终点 Y"]))
            if 90 < dim_angle < 180:
                dim_angle += 180
            elif 180 <= dim_angle <= 270:
                dim_angle -= 180
            # 覆盖测量文本
            if row["覆盖值"]:
                dim_text = row["覆盖值"]
            else:
                dim_text = row["值"]

            dim = msp.add_linear_dim(
                base=location,
                p1=p1,
                p2=p2,
                text=dim_text,
                dimstyle=dimstyle_name,  
                dxfattribs={"layer": layer, "color": color, "linetype": linetype, "lineweight": lineweight},
                angle=dim_angle
            )
            dim.render()
        except ValueError:
            messagebox.showwarning("警告",
                                   f"文件 {input_file} 第 {line_num} 行的 DIMENSION 实体线性尺寸坐标字段包含无效数据，将略过此数据。")
            logging.warning(
                f"文件 {input_file} 第 {line_num} 行的 DIMENSION 实体线性尺寸坐标字段包含无效数据，将略过此数据。")
    elif dim_type == 'ANGULAR':
        try:
            p1 = (float(row["起点 X"]), float(row["起点 Y"]))
            p2 = (float(row["终点 X"]), float(row["终点 Y"]))
            p3 = (float(row["圆心 X"]), float(row["圆心 Y"]))
            dim = msp.add_angular_dim3p(
                base=(0, 0),
                p1=p1,
                p2=p2,
                p3=p3,
                dimstyle=dimstyle_name,
                dxfattribs={"layer": layer, "color": color, "linetype": linetype, "lineweight": lineweight}
            )
            dim.render()
        except ValueError:
            messagebox.showwarning("警告",
                                   f"文件 {input_file} 第 {line_num} 行的 DIMENSION 实体角度尺寸坐标字段包含无效数据，将略过此数据。")
            logging.warning(
                f"文件 {input_file} 第 {line_num} 行的 DIMENSION 实体角度尺寸坐标字段包含无效数据，将略过此数据。")
    elif dim_type == 'DIAMETER':
        try:
            dim_value = float(row["值"])
            center = (float(row["圆心 X"]), float(row["圆心 Y"]))
            radius = dim_value / 2
            location = (float(row["位置 X"]), float(row["位置 Y"]))
            if row["覆盖值"]:
                dim_text = row["覆盖值"]
            else:
                dim_text = row["值"]
            dim = msp.add_diameter_dim(
                center=center,
                radius=radius,
                angle=dim_angle,
                # location=location,
                text=dim_text,
                dimstyle=dimstyle_name,
                dxfattribs={"layer": layer, "color": color, "linetype": linetype, "lineweight": lineweight},
                override={"dimtoh": 1, "dimtix": 0}
            )
            dim.render()
        except ValueError:
            messagebox.showwarning("警告",
                                   f"文件 {input_file} 第 {line_num} 行的 DIMENSION 实体直径尺寸坐标或值字段包含无效数据，将略过此数据。")
            logging.warning(
                f"文件 {input_file} 第 {line_num} 行的 DIMENSION 实体直径尺寸坐标或值字段包含无效数据，将略过此数据。")
    elif dim_type == 'RADIUS':
        try:
            dim_value = float(row["值"])
            center = (float(row["圆心 X"]), float(row["圆心 Y"]))
            radius = dim_value
            location = (float(row["位置 X"]), float(row["位置 Y"]))
            if row["覆盖值"]:
                dim_text = row["覆盖值"]
            else:
                dim_text = row["值"]
            dim = msp.add_radius_dim(
                center=center,
                radius=radius,
                angle=dim_angle,
                text=dim_text,
                dimstyle=dimstyle_name,
                # location=location,
                dxfattribs={"layer": layer, "color": color, "linetype": linetype, "lineweight": lineweight},
                override={"dimtoh": 1, "dimtix": 0}
            )
            dim.render()
        except ValueError:
            messagebox.showwarning("警告",
                                   f"文件 {input_file} 第 {line_num} 行的 DIMENSION 实体半径尺寸坐标或值字段包含无效数据，将略过此数据。")
            logging.warning(
                f"文件 {input_file} 第 {line_num} 行的 DIMENSION 实体半径尺寸坐标或值字段包含无效数据，将略过此数据。")


# 绘制圆弧函数
def handle_arc(row, msp, layer, color, linetype, lineweight, input_file, line_num):
    try:
        center = (float(row["圆心 X"]), float(row["圆心 Y"]))
        radius = float(row["半径"])
        start_angle = float(row["起始角度"])
        end_angle = float(row["终止角度"])
        msp.add_arc(center, radius, start_angle, end_angle,
                    dxfattribs={"layer": layer, "color": color, "linetype": linetype, "lineweight": lineweight})
    except (ValueError, TypeError):
        messagebox.showwarning("警告",
                               f"文件 {input_file} 第 {line_num} 行的 ARC 实体坐标、半径或角度字段包含无效数据，将略过此数据。")
        logging.warning(f"文件 {input_file} 第 {line_num} 行的 ARC 实体坐标、半径或角度字段包含无效数据，将略过此数据。")


# 绘制文本函数
def handle_text(row, msp, layer, color, input_file, entity_type, line_num):
    try:
        text_content = row["值"]
        text_location = (float(row["位置 X"]), float(row["位置 Y"]))
        text_height = float(row["高度"])
        text_rotation = float(row["角度"])
        if entity_type == 'TEXT':
            msp.add_text(
                text_content,
                dxfattribs={
                    "layer": layer,
                    "height": text_height,
                    "rotation": text_rotation,
                    "color": color,
                }
            ).set_pos(text_location)
        else:  # MTEXT
            msp.add_mtext(
                text_content,
                dxfattribs={
                    "layer": layer,
                    "char_height": text_height,
                    "rotation": text_rotation,
                    "color": color,
                    'style': 'CUSTOM_TEXTSTYLE'
                }
            ).set_location(text_location)
    except (ValueError, TypeError):
        messagebox.showwarning("警告",
                               f"文件 {input_file} 第 {line_num} 行的 {entity_type} 实体文本相关字段包含无效数据，将略过此数据。")
        logging.warning(
            f"文件 {input_file} 第 {line_num} 行的 {entity_type} 实体文本相关字段包含无效数据，将略过此数据。")


# 绘制剖面线函数
def handle_hatch(row, msp, layer, color, input_file, line_num):
    pattern_name = row["类型/名称"]
    boundary_vertices_str = row["顶点数据"]
    scale_str = row.get("缩放比例", "1.0")
    try:
        if pattern_name == "AR-CONC":
            scale = 0.1
        else:
            scale = safe_float(scale_str)
    except ValueError:
        messagebox.showwarning("警告",
                               f"文件 {input_file} 第 {line_num} 行的 HATCH 实体缩放比例字段 '{scale_str}' 不是有效的数字，将使用默认值 1.0。")
        logging.warning(
            f"文件 {input_file} 第 {line_num} 行的 HATCH 实体缩放比例字段 '{scale_str}' 不是有效的数字，将使用默认值 1.0。")
        scale = 1.0
    if not boundary_vertices_str:
        return
    boundary_vertices = []
    vertex_strs = boundary_vertices_str.split("; ")
    for vertex_str in vertex_strs:
        try:
            # 处理三元数组数据，假设格式为 (x, y, bulge)
            parts = vertex_str.strip("()").split(", ")
            if len(parts) == 2:
                x, y = parts
                bulge = 0
            elif len(parts) == 3:
                x, y, bulge = parts
            else:
                raise ValueError
            vertex = (float(x), float(y), float(bulge))
            boundary_vertices.append(vertex)
        except ValueError:
            messagebox.showwarning("警告",
                                   f"文件 {input_file} 第 {line_num} 行的 HATCH 实体边界顶点数据包含无效数据，将略过此数据。")
            logging.warning(
                f"文件 {input_file} 第 {line_num} 行的 HATCH 实体边界顶点数据包含无效数据，将略过此数据。")
            boundary_vertices = []
            break
    if boundary_vertices:
        hatch = msp.add_hatch(dxfattribs={"layer": layer})
        # 这里假设 ezdxf 支持带 bulge 值的路径
        hatch.paths.add_polyline_path(boundary_vertices, is_closed=True)
        hatch.set_pattern_fill(pattern_name, scale=scale, color=color)


# 块添加实体函数
def block_add_virtual_entities(data, block, block_name, input_file, dimstyle_name):
    # 将模型空间设为块
    msp = block
    for line_num, row in enumerate(data, start=2):  # 从第 2 行开始计数
        line_num -= 1
        # 读取块内元素
        if row["块名"] and row["实体类型"] != 'INSERT':
            if row["块名"].split(": ")[1] == block_name:
                try:
                    entity_type = row["实体类型"]
                    layer = row["图层"]
                    color = handle_color(row["颜色"])
                    linetype = row["线型"]
                    lineweight = int(row["线宽"])
                    if entity_type == 'LINE':
                        handle_line(row, msp, layer, color, linetype, lineweight, input_file, line_num)
                    elif entity_type == 'CIRCLE':
                        handle_circle(row, msp, layer, color, linetype, lineweight, input_file, line_num)
                    elif entity_type == 'LWPOLYLINE':
                        handle_lwpolyline(row, msp, layer, color, linetype, lineweight, input_file, line_num)
                    elif entity_type == 'DIMENSION':
                        handle_dimension(row, msp, layer, color, linetype, lineweight, input_file, line_num, dimstyle_name)
                    elif entity_type == 'ARC':
                        handle_arc(row, msp, layer, color, linetype, lineweight, input_file, line_num)
                    elif entity_type in ['TEXT', 'MTEXT']:
                        handle_text(row, msp, layer, color, input_file, entity_type, line_num)
                    elif entity_type == 'HATCH':
                        handle_hatch(row, msp, layer, color, input_file, line_num)
                except Exception as e:
                    messagebox.showwarning("警告", f"文件 {input_file} 第 {line_num} 行发生未知错误: {str(e)}，将略过此数据。")
                    logging.warning(f"文件 {input_file} 第 {line_num} 行发生未知错误: {str(e)}，将略过此数据。")


# 绘制块函数
def handle_insert(data, row, msp, doc, layer, color, linetype, lineweight, input_file, dimstyle_name):
    # 读取块名
    block_name = row["块名"].split(": ")[1]
    # 创建块
    block = doc.blocks.new(name=block_name)
    # 块添加实体
    block_add_virtual_entities(data, block, block_name, input_file, dimstyle_name)
    # 根据块引用添加块
    block_location = (float(row["位置 X"]), float(row["位置 Y"]))
    try:
        block_rotation = float(row["角度"])
    except ValueError:
        block_rotation = 0
    msp.add_blockref(block_name, block_location, dxfattribs={"layer": layer, "color": color,
                                                             "linetype": linetype, "lineweight": lineweight,
                                                             'rotation': block_rotation})