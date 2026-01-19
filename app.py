import os
import sys
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import tempfile
import csv
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加design目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'design'))

# 导入后端功能模块
try:
    from brb_drawing import brb_drawing
    from vfd_drawing import vfd_drawing
    from dxf_to_csv import dxf_to_csv
    from csv_to_dxf import csv_to_dxf
    from brb_materials import generate_materials_excel
    from refresh_brb_templates import refresh_brb_templates
    print("所有后端模块导入成功")
except Exception as e:
    print(f"导入后端模块时出错: {e}")
    import traceback
    traceback.print_exc()

app = Flask(__name__)

# 确保Flask应用正确处理UTF-8编码
app.config['JSON_AS_ASCII'] = False

# 配置CORS
CORS(app)

# 配置上传文件夹
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'dxf', 'csv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 确保上传文件夹存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 辅助函数：检查文件类型
def allowed_file(filename, allowed_extensions=None):
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# 健康检查端点
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'CAD-change API is running'})

# BRB图纸下载API
@app.route('/api/brb/drawing-download', methods=['POST'])
def brb_drawing_download_api():
    try:
        import io
        from brb_drawing import brb_drawing
        
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '无有效数据'}), 400
        
        project_name = data.get('projectName')
        parameter_table = data.get('parameterTable')
        total_quantity = data.get('totalQuantity')
        
        if not project_name or not parameter_table:
            return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
        
        # 转换数据格式以适应brb_drawing函数的要求
        width = int(parameter_table.get("width", 0))
        height = int(parameter_table.get("height", 0))
        thickness = int(parameter_table.get("thickness", 0))
        design_force = int(parameter_table.get("designForce", 0))
        tube_width = int(parameter_table.get("tubeWidth", 0))
        tube_thickness = int(parameter_table.get("tubeThickness", 0))
        weld = int(parameter_table.get("weld", 0))
        
        table_item = {
            "template": parameter_table.get("template", "王工"),  # 从前端获取模板，如果没有则使用默认值
            "project_name": project_name,
            "width": width,
            "height": height,
            "thickness": thickness,
            "force": design_force,
            "tube_width": tube_width,
            "tube_thickness": tube_thickness,
            "weld": weld,
            "core_material": parameter_table.get("coreMaterial", "Q235"),
            "length_quantity": [(int(lq.get("length", 0)), int(lq.get("quantity", 0))) 
                              for lq in parameter_table.get("lengthQuantityTable", [])]
        }
        
        # 调用BRB设计功能
        drawing_result = brb_drawing([table_item], None)
        
        if drawing_result and len(drawing_result) > 0:
            if isinstance(drawing_result[0], tuple):
                # 对于内存流，直接返回文件
                stream, filename = drawing_result[0]
                stream.seek(0)
                return send_file(
                    stream,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='application/dxf'
                )
            else:
                # 对于文件路径，读取文件内容并返回
                filepath = drawing_result[0]
                filename = os.path.basename(filepath)
                return send_file(
                    filepath,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='application/dxf'
                )
        else:
            return jsonify({'status': 'error', 'message': '生成图纸失败'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'下载图纸过程出错: {str(e)}'}), 500

# BRB设计API
@app.route('/api/brb/design', methods=['POST'])
def brb_design_api():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'error', 'message': '无有效数据'}), 400
        
        project_name = data.get('projectName')
        project_folder = data.get('projectFolder')
        parameter_tables = data.get('parameterTables')
        
        if not project_name or not parameter_tables:
            return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
        
        # 转换数据格式以适应现有功能
        data_table = []
        for i, table in enumerate(parameter_tables):
            # 确保table是字典类型
            if not isinstance(table, dict):
                continue
                
            # 确保所有数值参数都有有效的默认值
            width = int(table.get("width", 0))
            height = int(table.get("height", 0))
            thickness = int(table.get("thickness", 0))
            design_force = int(table.get("designForce", 0))
            tube_width = int(table.get("tubeWidth", 0))
            tube_thickness = int(table.get("tubeThickness", 0))
            weld = int(table.get("weld", 0))
            
            table_item = {
                "template": table.get("template"),  # 从前端获取模板，不设置默认值
                "project_name": project_name,
                "width": width,
                "height": height,
                "thickness": thickness,
                "force": design_force,
                "tube_width": tube_width,
                "tube_thickness": tube_thickness,
                "weld": weld,
                "core_material": table.get("coreMaterial", "Q235"),
                "design_force": design_force,
                "length_quantity": [(int(lq.get("length", 0)), int(lq.get("quantity", 0))) 
                                  for lq in table.get("lengthQuantityTable", [])]
            }
            data_table.append(table_item)
        
        # 调用BRB设计功能
        result = brb_drawing(data_table, project_folder)
        
        # 处理返回结果
        if project_folder:
            # 如果提供了project_folder，返回文件路径列表
            return jsonify({'status': 'success', 'message': 'BRB设计完成', 'result': result})
        else:
            # 如果没有提供project_folder，返回文件路径列表
            # 这里我们不直接返回文件流，而是让前端在需要时单独下载每个文件
            import io
            if result and len(result) > 0:
                if isinstance(result[0], tuple):
                    # 对于内存流，我们只返回文件名列表
                    # 前端在需要时会单独调用API下载每个文件
                    file_names = [filename for _, filename in result]
                    return jsonify({'status': 'success', 'message': 'BRB设计完成', 'result': file_names})
                else:
                    return jsonify({'status': 'success', 'message': 'BRB设计完成', 'result': result})
            else:
                return jsonify({'status': 'success', 'message': 'BRB设计完成', 'result': []})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'设计过程出错: {str(e)}'}), 500

# 粘滞产品设计API
@app.route('/api/vfd/design', methods=['POST'])
def vfd_design_api():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '无有效数据'}), 400
        
        project_name = data.get('projectName')
        project_folder = data.get('projectFolder')
        selected_model = data.get('selectedModel')
        parameters = data.get('parameters')
        
        if not project_name or not selected_model:
            return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
        
        # 调用粘滞产品设计功能
        result = vfd_drawing(project_name, selected_model, parameters, project_folder)
        
        return jsonify({'status': 'success', 'message': '粘滞产品设计完成', 'result': result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'设计过程出错: {str(e)}'}), 500

# BRB批量下载API
@app.route('/api/brb/batch-download', methods=['POST'])
def brb_batch_download_api():
    try:
        import zipfile
        import io
        from brb_drawing import brb_drawing
        from brb_materials import generate_materials_excel
        
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '无有效数据'}), 400
        
        project_name = data.get('projectName')
        parameter_tables = data.get('parameterTables')
        total_quantity = data.get('totalQuantity')
        file_types = data.get('fileTypes', [])
        table_indices = data.get('tableIndices', [])
        
        if not project_name or not parameter_tables:
            return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
        
        # 创建内存中的ZIP文件
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 处理每个文件
            for i, (file_type, table_index) in enumerate(zip(file_types, table_indices)):
                if file_type == 'materials':
                            # 生成材料单
                            # 转换数据格式以适应generate_materials_excel函数的要求
                            data_table = []
                            for table in parameter_tables:
                                # 确保所有数值参数都有有效的默认值
                                width = int(table.get("width", 0))
                                height = int(table.get("height", 0))
                                thickness = int(table.get("thickness", 0))
                                design_force = int(table.get("designForce", 0))
                                tube_width = int(table.get("tubeWidth", 0))
                                tube_thickness = int(table.get("tubeThickness", 0))
                                weld = int(table.get("weld", 0))
                                
                                table_item = {
                                    "template": table.get("template", "王工"),  # 从前端获取模板，如果没有则使用默认值
                                    "template_type": table.get("template_type", table.get("template", "王工")),  # 从前端获取template_type，如果没有则使用template的值
                                    "project_name": project_name,
                                    "core_material": table.get("coreMaterial", "Q235"),
                                    "design_force": design_force,
                                    "length_quantity": [(int(lq.get("length", 0)), int(lq.get("quantity", 0))) 
                                                      for lq in table.get("lengthQuantityTable", [])],
                                    # 按照brb_materials.py期望的格式创建params对象
                                    "params": {
                                        "板材厚度(mm)": str(thickness),
                                        "截面宽度(mm)": str(width),
                                        "截面高度(mm)": str(height),
                                        "焊缝高度(mm)": str(weld),
                                        "方管宽度(mm)": str(tube_width),
                                        "方管厚度(mm)": str(tube_thickness)
                                    }
                                }
                                data_table.append(table_item)
                            
                            materials_buffer = generate_materials_excel(project_name, data_table, None, None)
                            if isinstance(materials_buffer, io.BytesIO):
                                # 重置缓冲区指针到开始位置
                                materials_buffer.seek(0)
                                # 将材料单添加到ZIP文件
                                zipf.writestr(f'{project_name}_材料单.xlsx', materials_buffer.read())
                else:
                    # 生成图纸
                    if table_index is not None and table_index < len(parameter_tables):
                        # 只处理该文件对应的参数表
                        single_parameter_table = [parameter_tables[table_index]]
                        
                        # 转换数据格式
                        data_table = []
                        for table in single_parameter_table:
                            # 确保所有数值参数都有有效的默认值
                            width = int(table.get("width", 0))
                            height = int(table.get("height", 0))
                            thickness = int(table.get("thickness", 0))
                            design_force = int(table.get("designForce", 0))
                            tube_width = int(table.get("tubeWidth", 0))
                            tube_thickness = int(table.get("tubeThickness", 0))
                            weld = int(table.get("weld", 0))
                            
                            table_item = {
                                "template": table.get("template", "王工"),  # 从前端获取模板，如果没有则使用默认值
                                "project_name": project_name,
                                "width": width,
                                "height": height,
                                "thickness": thickness,
                                "force": design_force,
                                "tube_width": tube_width,
                                "tube_thickness": tube_thickness,
                                "weld": weld,
                                "core_material": table.get("coreMaterial", "Q235"),
                                "length_quantity": [(int(lq.get("length", 0)), int(lq.get("quantity", 0))) 
                                                  for lq in table.get("lengthQuantityTable", [])]
                            }
                            data_table.append(table_item)
                        
                        # 生成图纸
                        drawing_result = brb_drawing(data_table, None)
                        if drawing_result and len(drawing_result) > 0:
                            # 对于内存生成的图纸，结果是元组 (stream, filename)
                            if isinstance(drawing_result[0], tuple):
                                stream, filename = drawing_result[0]
                                stream.seek(0)
                                zipf.writestr(filename, stream.read())
                            # 对于实际文件路径，读取文件内容并添加到ZIP
                            else:
                                filepath = drawing_result[0]
                                filename = os.path.basename(filepath)
                                with open(filepath, 'rb') as f:
                                    zipf.writestr(filename, f.read())
        
        # 重置ZIP缓冲区指针到开始位置
        zip_buffer.seek(0)
        
        # 返回ZIP文件
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f'{project_name}_批量下载.zip',
            mimetype='application/zip'
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'批量下载过程出错: {str(e)}'}), 500

# BRB材料单生成API
@app.route('/api/brb/materials', methods=['POST'])
def brb_materials_api():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '无有效数据'}), 400
        
        project_name = data.get('projectName')
        project_folder = data.get('projectFolder', '')  # 如果没有提供projectFolder，默认使用空字符串
        parameter_tables = data.get('parameterTables')
        
        if not project_name or not parameter_tables:
            print("缺少必要参数")
            return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
        
        # 转换数据格式以适应现有功能
        data_table = []
        for table in parameter_tables:
            # 确保所有数值参数都有有效的默认值
            width = int(table.get("width", 0))
            height = int(table.get("height", 0))
            thickness = int(table.get("thickness", 0))
            design_force = int(table.get("designForce", 0))
            tube_width = int(table.get("tubeWidth", 0))
            tube_thickness = int(table.get("tubeThickness", 0))
            weld = int(table.get("weld", 0))
            
            table_item = {
                "template": table.get("template", "王工"),  # 从前端获取模板，如果没有则使用默认值
                "template_type": table.get("template_type", table.get("template", "王工")),  # 从前端获取template_type，如果没有则使用template的值
                "project_name": project_name,
                "core_material": table.get("coreMaterial", "Q235"),
                "design_force": design_force,
                "length_quantity": [(int(lq.get("length", 0)), int(lq.get("quantity", 0))) 
                                  for lq in table.get("lengthQuantityTable", [])],
                # 按照brb_materials.py期望的格式创建params对象
                "params": {
                    "板材厚度(mm)": str(thickness),
                    "截面宽度(mm)": str(width),
                    "截面高度(mm)": str(height),
                    "焊缝高度(mm)": str(weld),
                    "方管宽度(mm)": str(tube_width),
                    "方管厚度(mm)": str(tube_thickness)
                }
            }
            data_table.append(table_item)
        
        # 调用BRB材料单生成功能，但不保存到磁盘
        result = generate_materials_excel(project_name, data_table, project_folder=None, save_path=None)
        
        # 如果结果是BytesIO对象（内存中的Excel文件）
        import io
        if isinstance(result, io.BytesIO):
            # 设置文件名
            default_filename = f"{project_name}_材料单.xlsx"
            
            # 将内存中的Excel文件作为响应返回
            return send_file(
                result,
                as_attachment=True,
                download_name=default_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            # 如果仍然是文件路径（可能是测试或其他情况）
            return jsonify({'status': 'success', 'message': 'BRB材料单生成完成', 'result': result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'生成材料单过程出错: {str(e)}'}), 500

# DXF转CSV API
@app.route('/api/dxf/to/csv', methods=['POST'])
def dxf_to_csv_api():
    try:
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': '未找到上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': '未选择文件'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # 调用DXF转CSV功能
            csv_path = filepath.replace('.dxf', '.csv')
            csv_path = dxf_to_csv(filepath, csv_path)
            
            if csv_path and os.path.exists(csv_path):
                return send_file(csv_path, as_attachment=True)
            else:
                return jsonify({'status': 'error', 'message': '转换失败，未生成CSV文件'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'转换过程出错: {str(e)}'}), 500

# CSV转DXF API
@app.route('/api/csv/to/dxf', methods=['POST'])
def csv_to_dxf_api():
    try:
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': '未找到上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': '未选择文件'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # 调用CSV转DXF功能
            dxf_path = filepath.replace('.csv', '.dxf')
            dxf_path = csv_to_dxf(filepath, dxf_path)
            
            if dxf_path and os.path.exists(dxf_path):
                return send_file(dxf_path, as_attachment=True)
            else:
                return jsonify({'status': 'error', 'message': '转换失败，未生成DXF文件'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'转换过程出错: {str(e)}'}), 500

# CSV编辑API（保存）
@app.route('/api/csv/parse', methods=['POST'])
def csv_parse_api():
    try:
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': '未上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': '未选择文件'}), 400
        
        if file and allowed_file(file.filename, ['csv']):
            # 解析CSV文件
            csv_data = []
            headers = []
            
            # 使用csv模块读取文件
            file_content = file.read().decode('utf-8')
            reader = csv.DictReader(file_content.splitlines())
            
            headers = reader.fieldnames or []
            for row in reader:
                csv_data.append(row)
            
            return jsonify({'status': 'success', 'headers': headers, 'data': csv_data})
        else:
            return jsonify({'status': 'error', 'message': '文件格式不支持'}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'解析过程出错: {str(e)}'}), 500

@app.route('/api/csv/save', methods=['POST'])
def csv_save_api():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '无有效数据'}), 400
        
        filename = data.get('filename', 'edited.csv')
        csv_data = data.get('data', [])
        headers = data.get('headers', [])
        
        if not csv_data or not headers:
            return jsonify({'status': 'error', 'message': '无有效CSV数据或表头'}), 400
        
        # 创建临时文件保存CSV数据
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(csv_data)
            temp_filepath = f.name
        
        return send_file(temp_filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'保存过程出错: {str(e)}'}), 500

# 开发者密码验证API
@app.route('/api/verify/developer-password', methods=['POST'])
def verify_developer_password():
    try:
        data = request.get_json()
        password = data.get('password')
        
        if not password:
            return jsonify({'success': False, 'message': '密码不能为空'}), 400
        
        # 从环境变量获取正确的密码
        correct_password = os.environ.get('DEVELOPER_PASSWORD')
        
        if not correct_password:
            return jsonify({'success': False, 'message': '服务器配置错误，请联系管理员'}), 500
        
        if password == correct_password:
            return jsonify({'success': True, 'message': '密码验证成功'})
        else:
            return jsonify({'success': False, 'message': '密码错误，请重试'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'密码验证时出错: {str(e)}'}), 500

# 刷新BRB模版数据API
@app.route('/api/refresh/brb-templates', methods=['POST'])
def refresh_brb_templates_api():
    try:
        # 调用refresh_brb_templates函数
        success = refresh_brb_templates()
        
        if success:
            return jsonify({'success': True, 'message': 'BRB模版数据刷新成功'})
        else:
            return jsonify({'success': False, 'message': 'BRB模版数据刷新失败'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'刷新BRB模版数据时出错: {str(e)}'}), 500

# 文件下载API
@app.route('/api/download/file', methods=['GET'])
def download_file():
    try:
        # 获取文件路径参数
        file_path = request.args.get('path')
        if not file_path:
            return jsonify({'status': 'error', 'message': '缺少文件路径参数'}), 400
        
        # 验证文件路径是否安全（防止目录遍历攻击）
        # 只允许下载项目目录下的文件
        project_root = os.path.abspath(os.path.dirname(__file__))
        file_path = os.path.abspath(file_path)
        
        # 确保文件在项目根目录下
        if not file_path.startswith(project_root):
            return jsonify({'status': 'error', 'message': '文件路径不安全'}), 403
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'status': 'error', 'message': '文件不存在'}), 404
        
        # 获取文件名
        filename = os.path.basename(file_path)
        
        # 发送文件
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'下载过程出错: {str(e)}'}), 500

# 批量文件下载API
@app.route('/api/download/batch', methods=['POST'])
def batch_download_files():
    try:
        import zipfile
        
        # 获取文件路径列表
        data = request.get_json()
        file_paths = data.get('filePaths', [])
        
        if not file_paths or not isinstance(file_paths, list):
            return jsonify({'status': 'error', 'message': '缺少有效的文件路径列表'}), 400
        
        # 验证所有文件路径是否安全
        project_root = os.path.abspath(os.path.dirname(__file__))
        valid_file_paths = []
        
        for file_path in file_paths:
            abs_file_path = os.path.abspath(file_path)
            
            # 确保文件在项目根目录下
            if abs_file_path.startswith(project_root) and os.path.exists(abs_file_path):
                valid_file_paths.append(abs_file_path)
        
        if not valid_file_paths:
            return jsonify({'status': 'error', 'message': '没有有效的文件可以下载'}), 404
        
        # 创建临时ZIP文件
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.zip', delete=False) as temp_zip:
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_path in valid_file_paths:
                    # 获取文件名
                    filename = os.path.basename(file_path)
                    # 将文件添加到ZIP中
                    zf.write(file_path, filename)
            
            # 获取临时ZIP文件路径
            temp_zip_path = temp_zip.name
        
        # 发送ZIP文件
        return send_file(temp_zip_path, as_attachment=True, download_name='generated_files.zip')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'批量下载过程出错: {str(e)}'}), 500

# 文件删除API
@app.route('/api/download/delete', methods=['POST'])
def delete_file():
    try:
        # 获取要删除的文件路径
        data = request.get_json()
        file_path = data.get('filePath')
        
        if not file_path:
            return jsonify({'status': 'error', 'message': '缺少文件路径参数'}), 400
        
        # 验证文件路径是否安全（防止目录遍历攻击）
        project_root = os.path.abspath(os.path.dirname(__file__))
        abs_file_path = os.path.abspath(file_path)
        
        # 确保文件在项目根目录下
        if not abs_file_path.startswith(project_root):
            return jsonify({'status': 'error', 'message': '文件路径不安全'}), 403
        
        # 检查文件是否存在
        if not os.path.exists(abs_file_path):
            return jsonify({'status': 'error', 'message': '文件不存在'}), 404
        
        # 删除文件
        os.remove(abs_file_path)
        
        return jsonify({'status': 'success', 'message': '文件删除成功'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'文件删除过程出错: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000, host='0.0.0.0')