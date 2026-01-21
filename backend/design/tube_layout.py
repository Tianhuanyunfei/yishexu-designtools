import csv
import os
import logging

# 模拟messagebox模块，以确保csv_to_dxf在命令行环境中正常工作
try:
    import tkinter.messagebox as messagebox
except ImportError:
    # 在命令行环境中，创建一个模拟的messagebox模块
    class MockMessageBox:
        @staticmethod
        def showwarning(title, message):
            print(f"WARNING: {title}: {message}")
    messagebox = MockMessageBox()

# 添加当前目录到Python路径，确保能找到csv_to_dxf模块
import sys
sys.path.insert(0, os.path.dirname(__file__))

from csv_to_dxf import csv_to_dxf

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TubeLayoutGenerator:
    def __init__(self):
        pass
    
    def generate_tube_layout(self, project_name, parameter_tables):
        """
        生成方管排布图
        :param project_name: 项目名称
        :param parameter_tables: 参数表列表
        :return: 生成的文件路径列表
        """
        try:
            logging.info(f"开始生成方管排布图，项目名称: {project_name}")
            
            # 1. 处理所有参数表数据
            tube_data = self.process_frontend_data(parameter_tables)
            logging.info(f"处理后的数据: {tube_data}")
            
            if not tube_data:
                logging.warning("没有有效的方管数据")
                return []
            
            # 2. 按方管宽度分组
            grouped_tubes = self.group_by_tube_width(tube_data)
            logging.info(f"按方管宽度分组: {grouped_tubes}")
            
            # 3. 对每个宽度组生成切割方案
            all_cutting_plans = []
            for width, tubes in grouped_tubes.items():
                cutting_plan = self.generate_cutting_plan(tubes)
                all_cutting_plans.extend(cutting_plan)
            
            # 统计切割方案里所有方管的数量、总长度和余料总和
            total_tubes = 0
            total_length = 0
            total_leftover = 0
            total_unused_leftover = 0  # 仅统计不再使用的余料
            for plan in all_cutting_plans:
                total_tubes += plan['raw_materials']
                # 计算该方案的方管总长度，考虑raw_materials数量
                # 对于拼接方管，统计原需求长度（包括拼接的另一段）
                plan_length = 0
                for tube in plan['tubes']:
                    if 'original_length' in tube:
                        plan_length += tube['original_length']
                    else:
                        plan_length += tube['tube_length']
                total_length += plan_length * plan['raw_materials']
                # 计算该方案的余料总和，考虑raw_materials数量
                plan_leftover = plan['remaining_length'] * plan['raw_materials']
                total_leftover += plan_leftover
                
                # 仅统计不再使用的余料（没有被后续方案使用的余料）
                splice_info = plan.get('splice_info', {})
                to_plan = splice_info.get('to_plan')
                if to_plan is None or to_plan <= 0:
                    # 该余料没有被后续方案使用，统计到不再使用的余料总和中
                    total_unused_leftover += plan_leftover
            
            # 计算验证信息
            total_raw_length = total_tubes * 12000
            calculated_usage = total_raw_length - total_leftover
            
            logging.info(f"切割方案中所有方管的总数量: {total_tubes}")
            print(f"切割方案中所有方管的总数量: {total_tubes}")
            logging.info(f"所有方管的总长度（理论上）: {total_raw_length}mm")
            print(f"所有方管的总长度（理论上）: {total_raw_length}mm")
            logging.info(f"实际产品使用的方管总长度: {total_length}mm")
            print(f"实际产品使用的方管总长度: {total_length}mm")
            logging.info(f"总余料长度（包括被使用和不被使用的）: {total_leftover}mm")
            print(f"总余料长度（包括被使用和不被使用的）: {total_leftover}mm")
            logging.info(f"根据总长度和余料计算的使用长度: {calculated_usage}mm")
            print(f"根据总长度和余料计算的使用长度: {calculated_usage}mm")
            logging.info(f"不再使用的余料总和: {total_unused_leftover}mm")
            print(f"不再使用的余料总和: {total_unused_leftover}mm")
            
            # 4. 直接生成DXF文件
            dxf_file = self.convert_to_dxf(all_cutting_plans, project_name)
            logging.info(f"生成的DXF文件: {dxf_file}")
            
            return [dxf_file]
        except Exception as e:
            logging.error(f"生成方管排布图时出错: {e}")
            raise
    
    def process_frontend_data(self, parameter_tables):
        """
        处理前端数据
        :param parameter_tables: 参数表列表
        :return: 处理后的数据列表
        """
        tube_data = []
        
        for table in parameter_tables:
            # 获取方管宽度
            tube_width = int(table.get('tubeWidth', 0))
            if tube_width <= 0:
                continue
            
            # 获取屈服承载力
            yield_force = int(table.get('designForce', 0))
            
            # 处理长度-数量对应表
            length_quantity_table = table.get('lengthQuantityTable', [])
            for item in length_quantity_table:
                length = int(item.get('length', 0))
                quantity = int(item.get('quantity', 0))
                
                if length > 0 and quantity > 0:
                    # 方管长度 = 产品长度 - 300
                    tube_length = length - 300
                    if tube_length > 0:
                        tube_data.append({
                            'tube_width': tube_width,
                            'tube_length': tube_length,
                            'quantity': quantity,
                            'yield_force': yield_force,
                            'product_length': length
                        })
        
        return tube_data
    
    def group_by_tube_width(self, tube_data):
        """
        按方管宽度分组
        :param tube_data: 处理后的数据列表
        :return: 按方管宽度分组的数据
        """
        grouped = {}
        
        for item in tube_data:
            width = item['tube_width']
            if width not in grouped:
                grouped[width] = []
            grouped[width].append(item)
        
        return grouped
    
    def generate_cutting_plan(self, tubes):
        """
        生成切割方案
        :param tubes: 同一宽度的方管列表
        :return: 切割方案
        """
        # 原材长度
        raw_length = 12000
        
        # 按方管长度排序
        sorted_tubes = sorted(tubes, key=lambda x: x['tube_length'], reverse=True)
        
        # 生成切割方案
        cutting_plans = []
        plan_id = 1
        
        # 优化切割方案：组合不同长度的方管，以充分利用原材
        remaining_tubes = []
        for tube in sorted_tubes:
            for _ in range(tube['quantity']):
                remaining_tubes.append({
                    'tube_length': tube['tube_length'],
                    'product_length': tube['product_length'],
                    'yield_force': tube['yield_force'],
                    'tube_width': tube['tube_width']
                })
        
        # 余料拼接逻辑
        leftover = 0  # 上一根原材的剩余长度
        
        # 贪心算法：每次尝试填充一根原材
        while remaining_tubes:
            current_raw = []
            remaining_length = raw_length
            
            # 首先检查是否存在完美切割方案（正好用完原材长度），优先考虑完美方案
            # 检查当前是否可以组成完美切割方案
            perfect_cut_found = False
            
            # 只有当没有余料或者余料已被使用时，才考虑完美切割方案
            if leftover == 0 and remaining_tubes:
                # 统计剩余方管中每种长度的数量
                length_counts = {}
                for tube in remaining_tubes:
                    length = tube['tube_length']
                    if length in length_counts:
                        length_counts[length] += 1
                    else:
                        length_counts[length] = 1
                
                # 检查是否有某种长度的方管可以组成完美切割方案
                for tube_length, count in length_counts.items():
                    # 计算正好用完12000mm需要多少根这样的方管
                    num_tubes = raw_length // tube_length
                    if num_tubes > 0 and num_tubes * tube_length == raw_length:
                        # 可以组成完美切割方案，优先使用
                        if count >= num_tubes:
                            # 从剩余方管中取出num_tubes根该长度的方管
                            taken = 0
                            i = 0
                            while taken < num_tubes and i < len(remaining_tubes):
                                if remaining_tubes[i]['tube_length'] == tube_length:
                                    current_raw.append(remaining_tubes.pop(i))
                                    taken += 1
                                else:
                                    i += 1
                            remaining_length = 0  # 正好用完
                            perfect_cut_found = True
                            break
            
            # 如果没有找到完美切割方案，再考虑拼接余料
            if not perfect_cut_found:
                # 如果有余料且大于400mm，应用到当前原材的第一根方管
                if leftover > 400 and remaining_tubes:
                    # 尝试找到合适的方管来拼接余料
                    found = False
                    for i, tube in enumerate(remaining_tubes):
                        if tube['tube_length'] > leftover and tube['tube_length'] - leftover > 400:
                            # 创建拼接后的方管，记录拼接信息
                            spliced_tube = {
                                'tube_length': tube['tube_length'] - leftover,
                                'product_length': tube['product_length'],
                                'yield_force': tube['yield_force'],
                                'tube_width': tube['tube_width'],
                                'spliced_from': leftover,  # 记录拼接的放料长度
                                'original_length': tube['tube_length']  # 记录原需求长度
                            }
                            
                            # 使用拼接后的方管
                            current_raw.append(spliced_tube)
                            remaining_length -= spliced_tube['tube_length']
                            remaining_tubes.pop(i)
                            leftover = 0  # 余料已使用
                            found = True
                            break
                    
                    if not found:
                        # 如果没有找到合适的方管，放弃拼接，继续正常切割
                        leftover = 0
                
                # 尝试从剩余方管中选择合适的方管填充
                i = 0
                while i < len(remaining_tubes) and remaining_length > 0:
                    tube = remaining_tubes[i]
                    if tube['tube_length'] <= remaining_length:
                        current_raw.append(tube)
                        remaining_length -= tube['tube_length']
                        remaining_tubes.pop(i)
                    else:
                        i += 1
            
            # 为当前原材生成切割方案
            if current_raw:
                # 计算最终剩余长度
                final_leftover = remaining_length
                
                # 如果剩余长度大于400mm，保存为下一次拼接的余料
                if final_leftover > 400:
                    leftover = final_leftover
                else:
                    leftover = 0
                
                # 记录拼接关系
                splice_info = {
                    'from_plan': None,
                    'to_plan': None,
                    'length': 0
                }
                if leftover > 0:
                    splice_info['from_plan'] = plan_id
                    splice_info['length'] = leftover
                
                # 为当前原材生成切割方案
                cutting_plan = {
                    'plan_id': plan_id,
                    'tube_width': current_raw[0]['tube_width'],
                    'raw_length': raw_length,
                    'remaining_length': final_leftover,
                    'tubes': current_raw,
                    'pieces': len(current_raw),
                    'raw_materials': 1,
                    'splice': leftover > 0,
                    'splice_info': splice_info
                }
                
                cutting_plans.append(cutting_plan)
                
                # 如果下一个方案会使用当前方案的余料，记录目标方案
                if leftover > 0:
                    # 只有当还有剩余方管需要处理时，才设置to_plan
                    if remaining_tubes:
                        cutting_plan['splice_info']['to_plan'] = plan_id + 1
                plan_id += 1
        
        return cutting_plans
    
    def generate_csv(self, cutting_plans, project_name):
        """
        生成CSV文件
        :param cutting_plans: 切割方案
        :param project_name: 项目名称
        :return: CSV文件路径
        """
        # 创建CSV文件路径
        csv_dir = os.path.join(os.path.dirname(__file__), 'data', 'tube_layout')
        os.makedirs(csv_dir, exist_ok=True)
        
        # 确保项目名称是字符串，移除特殊字符
        project_name = str(project_name) if project_name else 'unnamed'
        # 移除可能导致路径问题的字符
        import re
        safe_project_name = re.sub(r'[^a-zA-Z0-9_-]', '', project_name)
        safe_project_name = safe_project_name[:20]  # 限制长度
        
        # 使用英文文件名，避免中文路径问题
        csv_file = os.path.join(csv_dir, f'{safe_project_name}_tube_layout.csv')
        
        # 写入CSV文件，使用UTF-8编码
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow([
                '实体类型', '图层', '颜色', '线型', '线宽', '线型描述', '线型图案',
                '类型/名称', '块名', '值', '覆盖值', '位置 X', '位置 Y',
                '起点 X', '起点 Y', '终点 X', '终点 Y',
                '圆心 X', '圆心 Y', '半径', '顶点数据', '闭合',
                '高度', '角度', '尺寸编码', '起始角度', '终止角度', '缩放比例', '尺寸样式'
            ])
            
            # 添加图层定义
            writer.writerow(['图层', '0', '7', 'CONTINUOUS', '0', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
            writer.writerow(['图层', 'TUBE', '3', 'CONTINUOUS', '50', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
            writer.writerow(['图层', 'TEXT', '3', 'CONTINUOUS', '0', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
            
            # 添加标注样式
            writer.writerow(['dimstyle', '', '', '', '', '', '', 'Standard', '', '{"dimtxt": 3.5, "dimclrd": 3, "dimasz": 4.0, "dimtad": 1, "dimjust": 0, "dimlwd": -2, "dimexo": 0.0, "dimscale": 1, "dimalt": 0, "dimadec": 2, "dimdsep": 44}', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
            
            # 计算总方管数量和总长度，考虑每个切割方案的raw_materials数量
            total_products = 0
            total_length = 0
            # 统计12米钢管的总根数
            total_raw_materials = 0
            for plan in cutting_plans:
                # 每个切割方案的原材数量
                raw_materials = plan['raw_materials']
                # 计算该方案的方管数量和长度，乘以原材数量
                plan_tubes = len(plan['tubes'])
                plan_length = sum(tube['tube_length'] for tube in plan['tubes'])
                
                total_products += plan_tubes * raw_materials
                total_length += plan_length * raw_materials
                total_raw_materials += raw_materials
            
            # 添加标题文本（使用英文，避免中文乱码）
            title = f"{safe_project_name} Tube Layout"
            subtitle = f"Total {total_raw_materials} raw materials, Total {total_products} tubes, Total length {total_length}mm"
            
            # 确保字段顺序与表头一致，并且所有字段都有值
            writer.writerow(['TEXT', 'TEXT', '3', 'CONTINUOUS', '0', '', '', '', '', title, '', '0', '1500', '', '', '', '', '', '', '', '', '50', '0', '', '', '', '', ''])
            writer.writerow(['TEXT', 'TEXT', '3', 'CONTINUOUS', '0', '', '', '', '', subtitle, '', '0', '1400', '', '', '', '', '', '', '', '', '30', '0', '', '', '', '', ''])
            
            # 绘制方管排列
            start_y = 1200
            y_step = 150
            
            for i, plan in enumerate(cutting_plans):
                y = start_y - i * y_step
                
                # 绘制原材线
                writer.writerow(['LINE', 'TUBE', '3', 'CONTINUOUS', '50', '', '', '', '', '', '', '', '', '0', str(y), str(plan['raw_length']), str(y), '', '', '', '', '', '', '', '', '', '', ''])
                
                # 绘制方管段
                current_x = 0
                for j, tube in enumerate(plan['tubes']):
                    length = tube['tube_length']
                    
                    # 绘制方管段
                    writer.writerow(['LINE', 'TUBE', '3', 'CONTINUOUS', '30', '', '', '', '', '', '', '', '', str(current_x), str(y-20), str(current_x + length), str(y-20), '', '', '', '', '', '', '', '', '', '', ''])
                    
                    # 绘制分割线
                    writer.writerow(['LINE', 'TUBE', '3', 'CONTINUOUS', '20', '', '', '', '', '', '', '', '', str(current_x + length), str(y-30), str(current_x + length), str(y+10), '', '', '', '', '', '', '', '', '', '', ''])
                    
                    # 添加方管信息
                    tube_info = f"{length}mm-{tube['yield_force']}KN"
                    text_x = current_x + length / 2
                    writer.writerow(['TEXT', 'TEXT', '3', 'CONTINUOUS', '0', '', '', '', '', tube_info, '', str(text_x), str(y-60), '', '', '', '', '', '', '', '', '20', '0', '', '', '', '', ''])
                    
                    current_x += length
                
                # 添加剩余长度信息
                remaining_info = f"Remain {plan['remaining_length']}mm"
                writer.writerow(['TEXT', 'TEXT', '3', 'CONTINUOUS', '0', '', '', '', '', remaining_info, '', str(plan['raw_length'] + 50), str(y), '', '', '', '', '', '', '', '', '20', '0', '', '', '', '', ''])
                
                # 添加原材编号
                raw_info = f"{i+1} pc"
                writer.writerow(['TEXT', 'TEXT', '3', 'CONTINUOUS', '0', '', '', '', '', raw_info, '', str(plan['raw_length'] / 2), str(y+30), '', '', '', '', '', '', '', '', '20', '0', '', '', '', '', ''])
        
        return csv_file
    
    def convert_to_dxf(self, cutting_plans, project_name):
        """
        将切割方案转换为DXF文件
        :param cutting_plans: 切割方案列表
        :param project_name: 项目名称
        :return: DXF文件路径
        """
        try:
            # 创建DXF文件路径
            dxf_dir = os.path.join(os.path.dirname(__file__), 'data', 'tube_layout')
            os.makedirs(dxf_dir, exist_ok=True)
            
            # 确保项目名称是字符串，移除特殊字符
            project_name = str(project_name) if project_name else 'unnamed'
            # 移除可能导致路径问题的字符
            import re
            safe_project_name = re.sub(r'[^a-zA-Z0-9_-]', '', project_name)
            safe_project_name = safe_project_name[:20]  # 限制长度
            
            # 使用英文文件名，避免中文路径问题
            dxf_file = os.path.join(dxf_dir, f'{safe_project_name}_tube_layout.dxf')
            
            # 合并相同的切割方案
            merged_plans = []
            plan_groups = {}
            
            for plan in cutting_plans:
                # 定义一个唯一的键来标识相同的切割方案
                # 包括：方管宽度、原材长度、方管段信息（长度、屈服力、拼接信息）
                key_parts = [
                    plan['tube_width'],
                    plan['raw_length'],
                    tuple((
                        tube['tube_length'],
                        tube['yield_force'],
                        tube.get('spliced_from'),
                        tube.get('original_length')
                    ) for tube in plan['tubes'])
                ]
                plan_key = tuple(key_parts)
                
                # 如果是相同的方案，增加数量
                if plan_key in plan_groups:
                    plan_groups[plan_key]['raw_materials'] += plan['raw_materials']
                else:
                    # 新建一个方案副本并添加到分组
                    plan_copy = plan.copy()
                    plan_copy['raw_materials'] = plan['raw_materials']
                    plan_groups[plan_key] = plan_copy
            
            # 将合并后的方案转换为列表
            merged_plans = list(plan_groups.values())
            
            return self.generate_dxf_directly(dxf_file, project_name, merged_plans)
        except Exception as e:
            logging.error(f"转换为DXF文件时出错: {e}")
            raise
    
    def generate_dxf_directly(self, dxf_file, project_name, cutting_plans):
        """
        直接生成DXF文件
        :param dxf_file: DXF文件路径
        :param project_name: 项目名称
        :param cutting_plans: 切割方案列表
        :return: DXF文件路径
        """
        try:
            import ezdxf
            import datetime
            
            # 生成带时间戳的文件名，避免文件锁定问题
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dxf_dir = os.path.dirname(dxf_file)
            base_name = os.path.basename(dxf_file)
            name_without_ext = os.path.splitext(base_name)[0]
            timestamped_name = f"{name_without_ext}_{timestamp}.dxf"
            dxf_file = os.path.join(dxf_dir, timestamped_name)
            
            # 创建一个新的DXF文档
            doc = ezdxf.new("R2018")
            msp = doc.modelspace()
            
            # 添加默认图层（不需要创建图层'0'，因为DXF默认包含）
            doc.layers.new("TUBE", dxfattribs={"color": 3})  # 绿色
            doc.layers.new("TEXT", dxfattribs={"color": 3})  # 绿色
            doc.layers.new("DIMENSION", dxfattribs={"color": 3})  # 绿色
            
            # 添加标注样式
            doc.dimstyles.add(
                name="Standard",
                dxfattribs={
                    "dimtxt": 3.5,  # 标注文字高度
                    "dimclrd": 0,   # 标注线颜色（0表示随层）
                    "dimasz": 4.0,  # 箭头大小
                    "dimtad": 1,    # 文字在尺寸线上方居中
                    "dimjust": 0,   # 尺寸线中间对齐
                    "dimlwd": -2,   # 标注线宽（-2表示默认宽度）
                    "dimexo": 0.0,  # 尺寸线超出尺寸界限的长度
                    "dimscale": 30,  # 标注比例
                    "dimalt": 0,    # 不使用替代单位
                    "dimadec": 2,   # 小数位数
                    "dimdsep": 44   # 小数分隔符（44是逗号）
                }
            )
            
            # 按方管宽度分组切割方案和统计信息
            grouped_plans = {}
            tube_stats = {}
            total_unused_leftover = 0  # 不再使用的余料总和（全局）
            
            for plan in cutting_plans:
                tube_width = plan['tube_width']
                
                # 分组切割方案
                if tube_width not in grouped_plans:
                    grouped_plans[tube_width] = []
                grouped_plans[tube_width].append(plan)
                
                # 统计信息
                if tube_width not in tube_stats:
                    tube_stats[tube_width] = {'count': 0, 'length': 0, 'raw_materials': 0, 'unused_leftover': 0}
                
                # 考虑每个切割方案的raw_materials数量
                raw_materials = plan['raw_materials']
                tube_count = len(plan['tubes'])
                tube_stats[tube_width]['count'] += tube_count * raw_materials
                tube_stats[tube_width]['raw_materials'] += raw_materials
                
                for tube in plan['tubes']:
                    # 如果是拼接方管，应该统计原需求长度（包括拼接的另一段）
                    if 'original_length' in tube:
                        # 拼接方管使用原需求长度
                        tube_length = tube['original_length']
                    else:
                        # 普通方管使用切割长度
                        tube_length = tube['tube_length']
                    tube_stats[tube_width]['length'] += tube_length * raw_materials
                
                # 统计不再使用的余料（余料就是不使用的料）
                splice_info = plan.get('splice_info', {})
                to_plan = splice_info.get('to_plan')
                if to_plan is None or to_plan <= 0:
                    plan_leftover = plan['remaining_length'] * raw_materials
                    tube_stats[tube_width]['unused_leftover'] += plan_leftover
                    total_unused_leftover += plan_leftover
            
            # 绘制每个宽度组的排布图
            current_y = 1500  # 初始y坐标
            
            # 按宽度排序
            for width in sorted(grouped_plans.keys()):
                plans = grouped_plans[width]
                
                # 计算当前宽度组的统计信息
                count = tube_stats[width]['count']
                length = tube_stats[width]['length']
                # 使用实际使用的根数之和，而不是基于总长度的理论需要根数
                raw_materials = tube_stats[width]['raw_materials']
                
                # 合并三行文本为一行，水平排列，中间用逗号隔开
                unused_leftover = tube_stats[width]['unused_leftover']
                # 合并文本：项目名称BRB, 方管总长需根数, 余料总和
                combined_text = f"{project_name} BRB, {width}方管总长{length}，需{raw_materials}根12米方管, 余料总和：{unused_leftover}mm"
                msp.add_text(
                    combined_text,
                    dxfattribs={
                        "layer": "TEXT",
                        "width": 0.8,
                        "height": 200,
                        "insert": (0, current_y)
                    }
                )
                current_y -= 250  # 恢复原来的行间距
                current_y -= 200  # 额外增加100间距，仅在文字和第一行钢管之间增加
                
                # 计算每个方案的余料长度，并按余料长度排序
                # 余料长度 = 原材长度 - 总切割长度
                for plan in plans:
                    # 计算总切割长度
                    total_cut_length = sum(tube['tube_length'] for tube in plan['tubes'])
                    # 原材长度为12000mm
                    raw_length = 12000
                    # 计算余料长度
                    remaining_length = raw_length - total_cut_length
                    plan['remaining_length'] = remaining_length
                
                # 首先识别完全不需要拼接的方案（没有拼接入和拼接出的方案）
                def is_splice_free(plan):
                    # 检查方案是否不使用其他方案的余料
                    uses_splice = any('spliced_from' in tube for tube in plan['tubes'])
                    # 检查方案是否不产生余料或余料≤400mm（不会被用于拼接）
                    produces_splice = plan['remaining_length'] > 400
                    # 完全不需要拼接的方案：不使用其他方案的余料，也不产生可被拼接的余料
                    return not uses_splice and not produces_splice
                
                # 分离方案：完全不需要拼接的方案和需要拼接的方案
                splice_free_plans = [plan for plan in plans if is_splice_free(plan)]
                plans_with_splice = [plan for plan in plans if not is_splice_free(plan)]
                
                # 对完全不需要拼接的方案进行排序：余料≤400的排在前面
                def sort_splice_free(plan):
                    return (0,) if plan['remaining_length'] <= 400 else (1,)
                
                sorted_splice_free_plans = sorted(splice_free_plans, key=sort_splice_free)
                
                # 处理需要拼接的方案：按拼接顺序排列
                # 创建一个字典来存储所有方案，方便查找
                plan_dict = {plan['plan_id']: plan for plan in plans_with_splice}
                
                # 创建拼接关系映射：key=plan_id_with_leftover, value=plan_id_that_uses_leftover
                splice_relations = {}
                
                # 创建一个集合来存储所有使用了其他方案余料的方案ID
                plans_that_use_splice = set()
                
                # 首先建立拼接关系映射
                for plan_with_splice in plans_with_splice:
                    if any('spliced_from' in tube for tube in plan_with_splice['tubes']):
                        # 找到该方案使用的余料长度
                        splice_length = next(tube['spliced_from'] for tube in plan_with_splice['tubes'] if 'spliced_from' in tube)
                        # 寻找产生该余料长度的方案
                        for plan_with_leftover in plans_with_splice:
                            if (plan_with_leftover['plan_id'] != plan_with_splice['plan_id'] and
                                plan_with_leftover['tube_width'] == plan_with_splice['tube_width'] and
                                plan_with_leftover['remaining_length'] == splice_length):
                                splice_relations[plan_with_leftover['plan_id']] = plan_with_splice['plan_id']
                                plans_that_use_splice.add(plan_with_splice['plan_id'])
                                break
                
                # 检查并处理方案合并可能导致的拼接关系丢失
                for plan_with_splice in plans_with_splice:
                    if (any('spliced_from' in tube for tube in plan_with_splice['tubes']) and
                        plan_with_splice['plan_id'] not in plans_that_use_splice):
                        for plan_with_leftover in plans_with_splice:
                            if (plan_with_leftover['plan_id'] != plan_with_splice['plan_id'] and
                                plan_with_leftover['tube_width'] == plan_with_splice['tube_width'] and
                                plan_with_leftover['remaining_length'] > 400):
                                # 检查是否有splice_info的关联
                                if ('splice_info' in plan_with_leftover and 
                                    plan_with_leftover['splice_info'].get('to_plan') == plan_with_splice['plan_id']):
                                    splice_relations[plan_with_leftover['plan_id']] = plan_with_splice['plan_id']
                                    plans_that_use_splice.add(plan_with_splice['plan_id'])
                                    break
                                # 检查是否有拼接管的original_length与余料长度的关系
                                if any('original_length' in tube and 
                                       tube['original_length'] - tube['tube_length'] == plan_with_leftover['remaining_length']
                                       for tube in plan_with_splice['tubes']):
                                    splice_relations[plan_with_leftover['plan_id']] = plan_with_splice['plan_id']
                                    plans_that_use_splice.add(plan_with_splice['plan_id'])
                                    break
                
                # 按拼接顺序排序需要拼接的方案
                reordered_plans_with_splice = []
                processed_plan_ids = set()
                
                # 首先添加不使用其他方案余料的方案（作为拼接链的起点）
                start_plans = [plan for plan in plans_with_splice if plan['plan_id'] not in plans_that_use_splice]
                
                # 对起点方案按余料≤400的排在前面排序
                def sort_start_plan(plan):
                    return (0,) if plan['remaining_length'] <= 400 else (1,)
                
                sorted_start_plans = sorted(start_plans, key=sort_start_plan)
                
                # 遍历起点方案，构建拼接链
                for plan in sorted_start_plans:
                    if plan['plan_id'] in processed_plan_ids:
                        continue
                        
                    # 添加当前方案
                    reordered_plans_with_splice.append(plan)
                    processed_plan_ids.add(plan['plan_id'])
                    
                    # 沿着拼接链继续添加后续方案
                    current_plan_id = plan['plan_id']
                    while current_plan_id in splice_relations:
                        next_plan_id = splice_relations[current_plan_id]
                        if next_plan_id not in processed_plan_ids:
                            next_plan = plan_dict[next_plan_id]
                            reordered_plans_with_splice.append(next_plan)
                            processed_plan_ids.add(next_plan_id)
                            current_plan_id = next_plan_id
                        else:
                            break
                
                # 添加剩余的需要拼接的方案（如果有的话）
                for plan in plans_with_splice:
                    if plan['plan_id'] not in processed_plan_ids:
                        reordered_plans_with_splice.append(plan)
                        processed_plan_ids.add(plan['plan_id'])
                
                # 构建最终的方案列表：先添加完全不需要拼接的方案，然后添加按拼接顺序排列的需要拼接的方案
                reordered_plans = sorted_splice_free_plans + reordered_plans_with_splice
                
                # 使用重新排序后的方案
                sorted_plans = reordered_plans
                
                # 绘制当前宽度组的切割方案
                for plan in sorted_plans:
                        
                    # 使用当前y坐标作为方管的垂直中心
                    y = current_y
                    
                    # 获取当前方管的高度（实际宽度值）
                    rect_height = int(plan['tube_width'])
                    
                    # 绘制方管段（白色粗实线矩形）
                    current_x = 0
                    # 在每个原材的开始部分添加宽度标注（每个原材只标注一次）
                    rect_height = int(plan['tube_width'])
                    rect_top = y + rect_height / 2
                    rect_bottom = y - rect_height / 2
                    # 标注的两个端点（方管的顶部和底部）
                    p1 = (current_x + 10, rect_bottom)  # 底部点
                    p2 = (current_x + 10, rect_top)  # 顶部点
                    # 标注的基准点位置
                    base = (current_x + 10 + 50, y)  # 标注文本的位置
                    # 创建线性标注
                    dim = msp.add_linear_dim(
                        base=base,
                        p1=p1,
                        p2=p2,
                        text=str(plan['tube_width']),
                        dimstyle="Standard",
                        dxfattribs={
                            "layer": "DIMENSION",
                            "color": 3,  # 绿色
                            "lineweight": 25
                        },
                        angle=90  # 垂直标注
                    )
                    dim.render()
                    
                    for j, tube in enumerate(plan['tubes']):
                        length = tube['tube_length']
                        product_length = tube['product_length']
                        
                        # 方管矩形的高度（使用实际的宽度值）
                        rect_height = int(plan['tube_width'])
                        rect_top = y + rect_height / 2
                        rect_bottom = y - rect_height / 2
                        
                        # 绘制方管矩形（使用四条线，白色粗实线）
                        # 上边
                        msp.add_line(
                            (current_x, rect_top),
                            (current_x + length, rect_top),
                            dxfattribs={"layer": "TUBE", "lineweight": 50, "color": 7}
                        )
                        # 下边
                        msp.add_line(
                            (current_x, rect_bottom),
                            (current_x + length, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 50, "color": 7}
                        )
                        
                        # 只绘制第一个方管段的左边
                        if j == 0:
                            msp.add_line(
                                (current_x, rect_top),
                                (current_x, rect_bottom),
                                dxfattribs={"layer": "TUBE", "lineweight": 50, "color": 7}
                            )
                        
                        # 绘制右边（作为下一个方管段的左边）
                        msp.add_line(
                            (current_x + length, rect_top),
                            (current_x + length, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 50, "color": 7}
                        )
                        
                        # 添加方管段长度标注（使用线性标注）
                        if 'spliced_from' in tube:
                            # 拼接方管的特殊标注格式：实际长度(+拼接长度=此方管需求长度）
                            dim_text = f"{length}(+{tube['spliced_from']}={tube['original_length']})"
                        else:
                            # 普通方管的标注格式
                            dim_text = f"{length}"
                        
                        # 线性标注的两个端点（方管段的左右两端）
                        p1 = (current_x, rect_top)  # 左端点
                        p2 = (current_x + length, rect_top)  # 右端点
                        # 标注的基准点位置（方管段上方中间）
                        base = (current_x + length / 2, y + rect_height / 2 + 50)  # 标注文本的位置
                        # 创建线性标注
                        dim = msp.add_linear_dim(
                            base=base,
                            p1=p1,
                            p2=p2,
                            text=dim_text,
                            dimstyle="Standard",
                            dxfattribs={
                                "layer": "DIMENSION",
                                "color": 3,  # 绿色
                                "lineweight": 25
                            },
                            angle=0  # 水平标注
                        )
                        dim.render()
                        
                        # 宽度标注已在原材开始部分添加，每个原材只标注一次
                        
                        # 在方管内部添加方管信息（删除单位，格式：BRB-屈服力-产品长度）
                        tube_info = f"BRB-{tube['yield_force']}-{product_length}"
                        # 设置文字居中对齐，确保文字位于方管水平和垂直中心
                        text_height = 120
                        # 计算文字宽度，估算每个字符的宽度为高度的0.5倍
                        text_width = len(tube_info) * text_height * 0.5
                        # 计算文字的插入点（左下角），使文字居中
                        insert_x = current_x + length / 2 - text_width / 2
                        insert_y = y - text_height / 2
                        msp.add_text(
                            tube_info,
                            dxfattribs={
                                "layer": "TEXT",
                                "height": text_height,
                                "insert": (insert_x, insert_y)
                            }
                        )
                        
                        current_x += length
                    
                    # 绘制剩余长度的矩形
                    if current_x < 12000:
                        remaining_length = 12000 - current_x
                        rect_top = y + rect_height / 2
                        rect_bottom = y - rect_height / 2
                        
                        # 绘制剩余长度矩形（使用四条线，白色粗实线）
                        # 上边
                        msp.add_line(
                            (current_x, rect_top),
                            (current_x + remaining_length, rect_top),
                            dxfattribs={"layer": "TUBE", "lineweight": 50, "color": 7}
                        )
                        # 下边
                        msp.add_line(
                            (current_x, rect_bottom),
                            (current_x + remaining_length, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 50, "color": 7}
                        )
                        # 左边
                        msp.add_line(
                            (current_x, rect_top),
                            (current_x, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 50, "color": 7}
                        )
                        # 右边
                        msp.add_line(
                            (current_x + remaining_length, rect_top),
                            (current_x + remaining_length, rect_bottom),
                            dxfattribs={"layer": "TUBE", "lineweight": 50, "color": 7}
                        )
                        
                        # 显示剩余长度信息（使用线性标注）
                        # 如果余料会被用作拼接，则不加"余"字；否则加"余"字
                        # 只有当该方案的余料确实被后续方案使用时，才不加"余"字
                        splice_info = plan.get('splice_info', {})
                        to_plan = splice_info.get('to_plan')
                        is_actually_spliced = to_plan is not None and to_plan > 0
                        
                        if is_actually_spliced:
                            remaining_text = f"{remaining_length}"
                        else:
                            remaining_text = f"余{remaining_length}"
                        
                        # 线性标注的两个端点（余料段的左右两端）
                        p1 = (current_x, rect_top)  # 左端点
                        p2 = (current_x + remaining_length, rect_top)  # 右端点
                        # 标注的基准点位置（余料段上方中间）
                        base = (current_x + remaining_length / 2, y + rect_height / 2 + 50)  # 标注文本的位置
                        # 创建线性标注
                        dim = msp.add_linear_dim(
                            base=base,
                            p1=p1,
                            p2=p2,
                            text=remaining_text,
                            dimstyle="Standard",
                            dxfattribs={
                                "layer": "DIMENSION",
                                "color": 3,  # 绿色
                                "lineweight": 25
                            },
                            angle=0  # 水平标注
                        )
                        dim.render()
                    
                    # 添加原材编号（显示该切割方案的实际数量）
                    raw_info = f"{plan['raw_materials']}根"
                    text_height = 120
                    # 计算方管下边缘位置：y - 方管高度的一半
                    tube_bottom = y - rect_height / 2
                    # 将原材数量放在方管下边缘下方，考虑文字高度（文字插入点是左下角）
                    text_y = tube_bottom - text_height - 50  # 增加50mm的间距
                    msp.add_text(
                        raw_info,
                        dxfattribs={
                            "layer": "TEXT",
                            "height": text_height,
                            "insert": (plan['raw_length'] / 2, text_y)
                        }
                    )
                    
                    # 计算下一个方管的垂直中心位置：当前方管底部 - 间距(450) - 下一个方管高度的一半
                    # 由于无法预知下一个方管的高度，使用当前方管的高度作为参考
                    # 确保方管之间的实际间距为450mm（缩小100）
                    current_y = y - rect_height / 2 - 450 - rect_height / 2
                
                # 不同宽度组之间的间隔
                current_y -= 2000
            
            # 添加全局不再使用的余料总和信息
            current_y -= 200
            msp.add_text(
                f"全局不再使用的余料总和：{total_unused_leftover}mm",
                dxfattribs={
                    "layer": "TEXT",
                    "width": 0.8,
                    "height": 200,
                    "insert": (0, current_y)
                }
            )
            
            # 保存DXF文件
            doc.saveas(dxf_file)
            print(f"DXF文件已成功保存: {dxf_file}")
            
            return dxf_file
        except Exception as e:
            logging.error(f"生成DXF文件时出错: {str(e)}")
            raise

# 测试代码
if __name__ == '__main__':
    generator = TubeLayoutGenerator()
    
    # 用户提供的测试数据
    test_json = {
        "projectName": "北京第二实验中学",
        "parameterTables": [
            {
                "id": "1",
                "designForce": "2000",
                "width": "150",
                "height": "150",
                "thickness": "20",
                "tubeWidth": "250",
                "tubeThickness": "4",
                "weld": "16",
                "coreMaterial": "LY225",
                "template": "王一",
                "lengthQuantityTable": [
                    {
                        "length": "5300",
                        "quantity": "1"
                    }
                ]
            },
            {
                "id": "1768544530827",
                "designForce": "2000",
                "width": "150",
                "height": "150",
                "thickness": "20",
                "tubeWidth": "200",
                "tubeThickness": "4",
                "weld": "16",
                "coreMaterial": "LY225",
                "template": "王一",
                "lengthQuantityTable": [
                    {
                        "length": "3000",
                        "quantity": "6"
                    },
                    {
                        "length": "2700",
                        "quantity": "88"
                    }
                ]
            },
            {
                "id": "1768544342107",
                "designForce": "1300",
                "width": "160",
                "height": "160",
                "thickness": "12",
                "tubeWidth": "200",
                "tubeThickness": "4",
                "weld": "10",
                "coreMaterial": "LY225",
                "template": "王一",
                "lengthQuantityTable": [
                    {
                        "length": "5100",
                        "quantity": "2"
                    },
                    {
                        "length": "4900",
                        "quantity": "14"
                    },
                    {
                        "length": "3200",
                        "quantity": "9"
                    },
                    {
                        "length": "3000",
                        "quantity": "14"
                    },
                    {
                        "length": "2800",
                        "quantity": "2"
                    },
                    {
                        "length": "2600",
                        "quantity": "7"
                    }
                ]
            },
            {
                "id": "1768544392549",
                "designForce": "1200",
                "width": "150",
                "height": "150",
                "thickness": "12",
                "tubeWidth": "200",
                "tubeThickness": "4",
                "weld": "10",
                "coreMaterial": "LY225",
                "template": "王一",
                "lengthQuantityTable": [
                    {
                        "length": "3600",
                        "quantity": "20"
                    },
                    {
                        "length": "3400",
                        "quantity": "16"
                    },
                    {
                        "length": "2700",
                        "quantity": "8"
                    }
                ]
            },
            {
                "id": "1768544410379",
                "designForce": "400",
                "width": "140",
                "height": "140",
                "thickness": "12",
                "tubeWidth": "200",
                "tubeThickness": "4",
                "weld": "10",
                "coreMaterial": "LY225",
                "template": "十一",
                "lengthQuantityTable": [
                    {
                        "length": "7100",
                        "quantity": "1"
                    },
                    {
                        "length": "4100",
                        "quantity": "1"
                    },
                    {
                        "length": "3700",
                        "quantity": "8"
                    },
                    {
                        "length": "2900",
                        "quantity": "5"
                    }
                ]
            }
        ],
        "totalQuantity": 202,
        "version": "1.0"
    }
    
    try:
        result = generator.generate_tube_layout(test_json['projectName'], test_json['parameterTables'])
        print(f"生成结果: {result}")
    except Exception as e:
        print(f"测试时出错: {e}")
        import traceback
        traceback.print_exc()
