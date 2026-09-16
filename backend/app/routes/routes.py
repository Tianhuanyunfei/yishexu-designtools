# 路由模块
import os
import sys
import csv
import json
import io
import tempfile
import zipfile
import uuid
from flask import request, jsonify, send_file
from werkzeug.utils import secure_filename

# 添加design目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'design'))

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# 导入日志模块
from app.utils.logger import app_logger

# 导入用户认证相关模块
from app.models.user import UserModel
from app.utils.auth import verify_password, get_password_hash, create_access_token, decode_access_token

# 导入后端功能模块
try:
    from brb_drawing import brb_drawing
    from vfd_drawing import vfd_drawing
    from dxf_to_csv import dxf_to_csv
    from csv_to_dxf import csv_to_dxf
    from brb_materials import generate_materials_excel
    from refresh_brb_templates import refresh_brb_templates
    from vfd_spec import (load_specs, load_basic_params, save_basic_params,
                          params_to_dict, spec_dir, _num_text)
    from vfd_geometry import build_preview, build_geometry, write_csv, axial_points, radial_values
    app_logger.info("所有后端模块导入成功")
except Exception as e:
    app_logger.error(f"导入后端模块时出错: {e}")
    import traceback
    traceback.print_exc()

# 导入工具函数
from app.utils.utils import allowed_file, validate_file_path
from config.config import Config
from app.services.workspace import WorkspaceStore

workspace_store = WorkspaceStore()


def get_current_user_id():
    authorization = request.headers.get('Authorization', '')
    if not authorization.startswith('Bearer '):
        return None
    payload = decode_access_token(authorization[7:].strip())
    if not payload:
        return None
    user_id = payload.get('sub')
    return user_id if UserModel().get_user_by_id(user_id) else None


# 注册所有路由
def register_routes(app):
    # 新文件中心：项目与版本化文件接口
    @app.route('/api/client/download', methods=['GET'])
    def client_download_api():
        client_path = os.path.abspath(os.path.join(Config.PROJECT_ROOT, '..', 'client_download', '羿射旭本地文件客户端.exe'))
        if not os.path.isfile(client_path):
            return jsonify({'status': 'error', 'message': '本地客户端安装包不存在'}), 404
        return send_file(
            client_path,
            as_attachment=True,
            download_name='羿射旭本地文件客户端.exe',
        )

    @app.route('/api/workspace/projects', methods=['GET'])
    def workspace_projects_api():
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        return jsonify({'status': 'success', 'projects': workspace_store.list_projects(user_id)})

    @app.route('/api/workspace/projects', methods=['POST'])
    def workspace_create_project_api():
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        data = request.get_json() or {}
        name = str(data.get('name', '')).strip()
        if not name:
            return jsonify({'status': 'error', 'message': '项目名称不能为空'}), 400
        project = workspace_store.create_project(name, user_id, str(data.get('description', '')).strip())
        return jsonify({'status': 'success', 'project': project}), 201

    @app.route('/api/workspace/projects/<project_id>/members', methods=['POST'])
    def workspace_add_member_api(project_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        data = request.get_json() or {}
        target_user_id = str(data.get('user_id', '')).strip()
        role = str(data.get('role', 'editor')).strip()
        project = workspace_store.add_member(project_id, user_id, target_user_id, role)
        if not project:
            return jsonify({'status': 'error', 'message': '无权添加成员或项目不存在'}), 403
        return jsonify({'status': 'success', 'project': project})

    @app.route('/api/workspace/projects/<project_id>/files', methods=['GET'])
    def workspace_files_api(project_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        parent_path = request.args.get('path', '')
        files = workspace_store.list_files(project_id, user_id, parent_path)
        if files is None:
            return jsonify({'status': 'error', 'message': '无权访问项目'}), 403
        return jsonify({'status': 'success', 'files': files})

    @app.route('/api/workspace/projects/<project_id>/directories', methods=['GET'])
    def workspace_directories_api(project_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        directories = workspace_store.list_directories(project_id, user_id)
        if directories is None:
            return jsonify({'status': 'error', 'message': '无权访问项目'}), 403
        return jsonify({'status': 'success', 'directories': directories})

    @app.route('/api/workspace/files/<file_id>/content', methods=['GET'])
    def workspace_download_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        file_entry = workspace_store.get_file(file_id, user_id)
        if not file_entry:
            return jsonify({'status': 'error', 'message': '文件不存在或无权访问'}), 404
        return send_file(
            io.BytesIO(workspace_store.get_current_content(file_entry)),
            as_attachment=True,
            download_name=file_entry['name'],
        )

    @app.route('/api/workspace/files/<file_id>/checkout/download', methods=['GET'])
    def workspace_checkout_download_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        checkout_token = request.args.get('checkout_token', '')
        lock = workspace_store.get_lock(file_id)
        if not lock:
            return jsonify({'status': 'error', 'message': '文件当前没有有效检出记录'}), 409
        if lock.get('user_id') != user_id or lock.get('token') != checkout_token:
            return jsonify({'status': 'error', 'message': '检出令牌无效'}), 403
        file_entry = workspace_store.get_file(file_id, user_id)
        if not file_entry:
            return jsonify({'status': 'error', 'message': '文件不存在或无权访问'}), 404
        # 基于历史版本检出时，下载的应是该历史版本内容，而不是当前最新版本。
        source_version_id = lock.get('source_version_id')
        if source_version_id:
            content = workspace_store.get_version_content(file_id, user_id, source_version_id)
            if content is None:
                return jsonify({'status': 'error', 'message': '检出所依据的历史版本已丢失'}), 409
            download_name = f"v{lock.get('source_version')}_{file_entry['name']}"
        else:
            content = workspace_store.get_current_content(file_entry)
            download_name = file_entry['name']
        return send_file(io.BytesIO(content), as_attachment=True, download_name=download_name)
    @app.route('/api/workspace/projects/<project_id>/files', methods=['POST'])
    def workspace_upload_api(project_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        uploaded = request.files.get('file')
        if not uploaded:
            return jsonify({'status': 'error', 'message': '缺少文件'}), 400
        relative_path = request.form.get('relative_path', uploaded.filename or '')
        base_version = request.form.get('base_version')
        lock_token = request.form.get('lock_token')
        result = workspace_store.save_file(project_id, user_id, relative_path, uploaded.read(), int(base_version) if base_version else None, lock_token)
        if result['status'] == 'conflict':
            return jsonify(result), 409
        if result['status'] == 'locked':
            return jsonify(result), 423
        if result['status'] in ('forbidden', 'invalid_path'):
            return jsonify(result), 403 if result['status'] == 'forbidden' else 400
        return jsonify(result), 201


    @app.route('/api/workspace/files/<file_id>/checkout', methods=['POST'])
    def workspace_checkout_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        data = request.get_json(silent=True) or {}
        version_id = str(data.get('version_id') or '')
        result, status = workspace_store.checkout(file_id, user_id, version_id or None)
        if status == 'not_found':
            return jsonify({'status': 'error', 'message': '文件或指定版本不存在'}), 404
        if status == 'forbidden':
            return jsonify({'status': 'error', 'message': '当前角色无权检出文件'}), 403
        if status == 'locked':
            return jsonify({'status': 'locked', 'message': '文件已被其他用户检出', 'lock': result}), 423
        return jsonify({'status': 'success', **result})

    @app.route('/api/workspace/files/<file_id>/checkin', methods=['POST'])
    def workspace_checkin_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        uploaded = request.files.get('file')
        checkout_token = request.form.get('checkout_token', '')
        base_version = request.form.get('base_version')
        checkout_version = request.form.get('checkout_version', base_version)
        if not uploaded or not checkout_token or checkout_version is None:
            return jsonify({'status': 'error', 'message': '缺少检入文件、检出令牌或检出版本'}), 400
        result = workspace_store.checkin(file_id, user_id, checkout_token, checkout_version, uploaded.read())
        if result['status'] == 'not_found':
            return jsonify({'status': 'error', 'message': '文件不存在'}), 404
        if result['status'] == 'forbidden':
            return jsonify({'status': 'error', 'message': '检出不属于当前用户或令牌无效'}), 403
        if result['status'] in ('conflict', 'invalid_lock'):
            message = '文件版本已变化，无法检入' if result['status'] == 'conflict' else '文件当前没有有效检出记录'
            return jsonify({**result, 'message': message}), 409
        if result['status'] == 'storage_error':
            return jsonify({**result, 'message': '服务器保存文件失败'}), 500
        return jsonify(result), 201

    @app.route('/api/workspace/files/<file_id>/cancel-checkout', methods=['POST'])
    def workspace_cancel_checkout_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        data = request.get_json(silent=True) or {}
        checkout_token = str(data.get('checkout_token') or data.get('token', ''))
        if not checkout_token:
            return jsonify({'status': 'error', 'message': '缺少检出令牌'}), 400
        status = workspace_store.cancel_checkout(file_id, user_id, checkout_token)
        if status == 'not_found':
            return jsonify({'status': 'error', 'message': '文件不存在'}), 404
        if status == 'forbidden':
            return jsonify({'status': 'error', 'message': '检出不属于当前用户或令牌无效'}), 403
        if status == 'invalid_lock':
            return jsonify({'status': 'error', 'message': '文件当前没有有效检出记录'}), 409
        return jsonify({'status': 'success'})

    @app.route('/api/workspace/files/<file_id>/checkout/heartbeat', methods=['POST'])
    def workspace_checkout_heartbeat_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        token = str((request.get_json(silent=True) or {}).get('token', ''))
        result = workspace_store.touch_checkout(file_id, user_id, token)
        if result == 'invalid_lock':
            return jsonify({'status': 'error', 'message': '文件当前没有有效检出记录'}), 409
        if result == 'forbidden':
            return jsonify({'status': 'error', 'message': '检出不属于当前用户或令牌无效'}), 403
        return jsonify({'status': 'success', 'lock': result})

    @app.route('/api/workspace/files/<file_id>/versions', methods=['GET'])
    def workspace_versions_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        versions = workspace_store.list_versions(file_id, user_id)
        if versions is None:
            return jsonify({'status': 'error', 'message': '文件不存在或无权访问'}), 404
        return jsonify({'status': 'success', 'versions': versions})

    @app.route('/api/workspace/files/<file_id>/versions/<version_id>/content', methods=['GET'])
    def workspace_version_download_api(file_id, version_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        version = workspace_store.get_version(file_id, user_id, version_id)
        if not version:
            return jsonify({'status': 'error', 'message': '历史版本不存在或无权访问'}), 404
        content = workspace_store.get_version_content(file_id, user_id, version_id)
        if content is None:
            return jsonify({'status': 'error', 'message': '历史版本文件已丢失'}), 404
        file_entry = workspace_store.get_file(file_id, user_id)
        name = file_entry['name'] if file_entry else 'version'
        return send_file(
            io.BytesIO(content),
            as_attachment=True,
            download_name=f"v{version['version']}_{name}",
        )


    @app.route('/api/workspace/files/<file_id>/lock', methods=['POST', 'DELETE'])
    def workspace_lock_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        if request.method == 'POST':
            result, status = workspace_store.acquire_lock(file_id, user_id)
            if status == 'not_found':
                return jsonify({'status': 'error', 'message': '文件不存在'}), 404
            if status == 'locked':
                return jsonify({'status': 'locked', 'lock': result}), 423
            return jsonify({'status': 'success', 'lock': result})
        data = request.get_json() or {}
        if workspace_store.release_lock(file_id, user_id, data.get('token', '')):
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': '锁不存在或不属于当前用户'}), 403

    @app.route('/api/workspace/files/<file_id>', methods=['DELETE'])
    def workspace_delete_file_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        status = workspace_store.delete_file(file_id, user_id)
        if status == 'not_found':
            return jsonify({'status': 'error', 'message': '文件不存在'}), 404
        if status == 'forbidden':
            return jsonify({'status': 'error', 'message': '当前角色无权删除文件'}), 403
        if status == 'locked':
            return jsonify({'status': 'error', 'message': '文件已被其他用户检出，无法删除'}), 423
        return jsonify({'status': 'success'})

    @app.route('/api/workspace/projects/<project_id>/directories', methods=['POST'])
    def workspace_create_directory_api(project_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        data = request.get_json(silent=True) or {}
        relative_path = str(data.get('path', '')).strip()
        status = workspace_store.create_directory(project_id, user_id, relative_path)
        if status == 'invalid_path':
            return jsonify({'status': 'error', 'message': '目录名称不合法'}), 400
        if status == 'exists':
            return jsonify({'status': 'error', 'message': '同名文件或目录已存在'}), 409
        if status == 'forbidden':
            return jsonify({'status': 'error', 'message': '当前角色无权新建目录'}), 403
        return jsonify({'status': 'success'}), 201

    @app.route('/api/workspace/projects/<project_id>/directories', methods=['DELETE'])
    def workspace_delete_directory_api(project_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        data = request.get_json(silent=True) or {}
        relative_path = str(data.get('path', '')).strip()
        status = workspace_store.delete_directory(project_id, user_id, relative_path)
        if status == 'invalid_path':
            return jsonify({'status': 'error', 'message': '目录路径不能为空'}), 400
        if status == 'not_found':
            return jsonify({'status': 'error', 'message': '目录不存在或已删除'}), 404
        if status == 'forbidden':
            return jsonify({'status': 'error', 'message': '当前角色无权删除目录'}), 403
        if status == 'locked':
            return jsonify({'status': 'error', 'message': '目录中存在被其他用户检出的文件，无法删除'}), 423
        return jsonify({'status': 'success'})

    @app.route('/api/workspace/projects/<project_id>/trash', methods=['GET'])
    def workspace_trash_api(project_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        files = workspace_store.list_trash(project_id, user_id)
        if files is None:
            return jsonify({'status': 'error', 'message': '无权访问项目'}), 403
        return jsonify({'status': 'success', 'files': files})

    @app.route('/api/workspace/files/<file_id>/restore', methods=['POST'])
    def workspace_restore_file_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        status = workspace_store.restore_entry(file_id, user_id)
        if status == 'not_found':
            return jsonify({'status': 'error', 'message': '回收站中不存在该文件或目录'}), 404
        if status == 'forbidden':
            return jsonify({'status': 'error', 'message': '当前角色无权恢复'}), 403
        if status == 'conflict':
            return jsonify({'status': 'error', 'message': '原路径已存在同名文件，请先处理后再恢复'}), 409
        return jsonify({'status': 'success'})

    @app.route('/api/workspace/files/<file_id>/purge', methods=['DELETE'])
    def workspace_purge_file_api(file_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        status = workspace_store.purge_entry(file_id, user_id)
        if status == 'not_found':
            return jsonify({'status': 'error', 'message': '回收站中不存在该文件或目录'}), 404
        if status == 'forbidden':
            return jsonify({'status': 'error', 'message': '当前角色无权彻底删除'}), 403
        return jsonify({'status': 'success'})

    @app.route('/api/workspace/projects/<project_id>/trash', methods=['DELETE'])
    def workspace_empty_trash_api(project_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        result = workspace_store.empty_trash(project_id, user_id)
        if result == 'forbidden':
            return jsonify({'status': 'error', 'message': '当前角色无权清空回收站'}), 403
        return jsonify({'status': 'success', 'count': result})

    @app.route('/api/workspace/projects/<project_id>', methods=['DELETE'])
    def workspace_delete_project_api(project_id):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'status': 'error', 'message': '需要登录'}), 401
        status = workspace_store.delete_project(project_id, user_id)
        if status == 'not_found':
            return jsonify({'status': 'error', 'message': '项目不存在'}), 404
        if status == 'forbidden':
            return jsonify({'status': 'error', 'message': '只有项目创建者可以删除项目'}), 403
        return jsonify({'status': 'success'})


    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'ok', 'message': 'yishexu-designtools API is running'})

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
                "template": parameter_table.get("template", "王（工）"),  # 从前端获取模板，如果没有则使用默认值
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
                # 如果没有提供project_folder，统一返回可直接下载的文件信息
                # 避免前端下载时再次调用图纸生成逻辑导致重复计算。
                if not result:
                    return jsonify({'status': 'success', 'message': 'BRB设计完成', 'result': []})

                files_info = []
                upload_folder = app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)

                for item in result:
                    # brb_drawing 在无 project_folder 时返回 (BytesIO, filename)
                    if isinstance(item, tuple) and len(item) == 2:
                        stream, filename = item
                        safe_name = secure_filename(filename) or f'brb_{uuid.uuid4().hex}.dxf'
                        if not safe_name.lower().endswith('.dxf'):
                            safe_name = f'{safe_name}.dxf'
                        stored_name = f'{uuid.uuid4().hex}_{safe_name}'
                        stored_path = os.path.join(upload_folder, stored_name)

                        stream.seek(0)
                        with open(stored_path, 'wb') as f:
                            f.write(stream.read())

                        files_info.append({
                            'name': filename,
                            'path': stored_path
                        })
                    elif isinstance(item, str):
                        files_info.append({
                            'name': os.path.basename(item),
                            'path': item
                        })

                return jsonify({'status': 'success', 'message': 'BRB设计完成', 'result': files_info})
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

    # ---------------------------------------------------------------- 粘滞阻尼器 VFD
    @app.route('/api/vfd/specs', methods=['GET'])
    def vfd_specs_api():
        """规格库：缸径/轴径组合列表。"""
        try:
            specs = load_specs()
            result = []
            for item in specs:
                params = load_basic_params(item['bore'], item['axis'])
                result.append({
                    'bore': item['bore'],
                    'axis': item['axis'],
                    'label': '缸径%s-轴径%s' % (_num_text(item['bore']), _num_text(item['axis'])),
                    'available': len(params) > 0,
                })
            return jsonify({'status': 'success', 'specs': result})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'读取规格表出错: {str(e)}'}), 500

    @app.route('/api/vfd/params', methods=['GET'])
    def vfd_params_api():
        """某规格的零件尺寸表。"""
        try:
            bore = request.args.get('bore', '')
            axis = request.args.get('axis', '')
            if not bore or not axis:
                return jsonify({'status': 'error', 'message': '缺少缸径或轴径'}), 400
            params = load_basic_params(bore, axis)
            return jsonify({'status': 'success', 'params': params})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'读取零件尺寸出错: {str(e)}'}), 500

    @app.route('/api/vfd/params', methods=['POST'])
    def vfd_params_save_api():
        """保存某规格的零件尺寸表（只覆盖传入的键）。"""
        try:
            data = request.get_json() or {}
            bore = data.get('bore', '')
            axis = data.get('axis', '')
            values = data.get('values') or {}
            if not bore or not axis:
                return jsonify({'status': 'error', 'message': '缺少缸径或轴径'}), 400
            params = save_basic_params(bore, axis, values)
            return jsonify({'status': 'success', 'message': '零件尺寸已保存', 'params': params})
        except FileNotFoundError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 404
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'保存零件尺寸出错: {str(e)}'}), 500

    @app.route('/api/vfd/preview', methods=['POST'])
    def vfd_preview_api():
        """结构图几何预览：参数 -> 几何实体 + 包围盒（前端画 SVG）。"""
        try:
            data = request.get_json() or {}
            bore = data.get('bore')
            axis = data.get('axis')
            values = data.get('values') or None
            displacement = data.get('displacement')
            clearance = data.get('clearance')
            overrides = data.get('overrides')

            if values is None:
                if bore is None or axis is None:
                    return jsonify({'status': 'error', 'message': '缺少参数'}), 400
                values = params_to_dict(load_basic_params(bore, axis))
                if not values:
                    return jsonify({'status': 'error', 'message': '该规格暂无基本尺寸表'}), 404

            # 设计位移、腔体余量为输入参数，不走基本尺寸表，随请求注入参与推导
            if displacement not in (None, ''):
                values['设计位移'] = displacement
            if clearance not in (None, ''):
                values['腔体余量'] = clearance

            preview = build_preview(values, overrides)
            return jsonify({'status': 'success', 'preview': preview})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'生成预览出错: {str(e)}'}), 500

    @app.route('/api/vfd/structure-dxf', methods=['POST'])
    def vfd_structure_dxf_api():
        """结构图 DXF：参数 -> CSV -> DXF，返回可下载文件信息。"""
        temp_csv = None
        try:
            data = request.get_json() or {}
            bore = data.get('bore')
            axis = data.get('axis')
            values = data.get('values') or None
            displacement = data.get('displacement')
            clearance = data.get('clearance')
            overrides = data.get('overrides')

            if values is None:
                if bore is None or axis is None:
                    return jsonify({'status': 'error', 'message': '缺少参数'}), 400
                values = params_to_dict(load_basic_params(bore, axis))
                if not values:
                    return jsonify({'status': 'error', 'message': '该规格暂无基本尺寸表'}), 404

            # 设计位移、腔体余量为输入参数，不走基本尺寸表，随请求注入参与推导
            if displacement not in (None, ''):
                values['设计位移'] = displacement
            if clearance not in (None, ''):
                values['腔体余量'] = clearance

            entities, _x, _r = build_geometry(values, overrides)

            upload_folder = app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)

            model_name = str(data.get('modelName') or '').strip()
            if not model_name:
                model_name = 'VFD-%s-%s' % (_num_text(bore), _num_text(axis))
            safe_name = secure_filename(model_name) or 'vfd_structure'

            temp_csv = os.path.join(upload_folder, f'{uuid.uuid4().hex}.csv')
            write_csv(entities, temp_csv)

            dxf_path = os.path.join(upload_folder, f'{uuid.uuid4().hex}_{safe_name}.dxf')
            csv_to_dxf(temp_csv, dxf_path)

            if not dxf_path or not os.path.isfile(dxf_path):
                return jsonify({'status': 'error', 'message': 'DXF 生成失败'}), 500

            return jsonify({
                'status': 'success',
                'message': '结构图生成完成',
                'result': {
                    'name': f'{safe_name}_结构图.dxf',
                    'path': dxf_path,
                }
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'生成结构图出错: {str(e)}'}), 500
        finally:
            if temp_csv and os.path.isfile(temp_csv):
                try:
                    os.remove(temp_csv)
                except OSError:
                    pass

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
                    "template": table.get("template", "王（工）"),  # 从前端获取模板，如果没有则使用默认值
                    "template_type": table.get("template_type", table.get("template", "王（工）")),  # 从前端获取template_type，如果没有则使用template的值
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
            
            # 调用BRB材料单生成功能
            result = generate_materials_excel(project_name, data_table, project_folder=None, save_path=None)

            # 统一返回可下载的文件信息，避免前端下载时再次触发生成
            default_filename = f"{project_name}_材料单.xlsx"
            upload_folder = app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)

            import io
            if isinstance(result, io.BytesIO):
                safe_name = secure_filename(default_filename) or f'brb_materials_{uuid.uuid4().hex}.xlsx'
                if not safe_name.lower().endswith('.xlsx'):
                    safe_name = f'{safe_name}.xlsx'
                stored_name = f'{uuid.uuid4().hex}_{safe_name}'
                stored_path = os.path.join(upload_folder, stored_name)

                result.seek(0)
                with open(stored_path, 'wb') as f:
                    f.write(result.read())

                return jsonify({
                    'status': 'success',
                    'message': 'BRB材料单生成完成',
                    'result': {
                        'name': default_filename,
                        'path': stored_path
                    }
                })

            if isinstance(result, str):
                return jsonify({
                    'status': 'success',
                    'message': 'BRB材料单生成完成',
                    'result': {
                        'name': os.path.basename(result),
                        'path': result
                    }
                })

            return jsonify({'status': 'success', 'message': 'BRB材料单生成完成', 'result': None})
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
            correct_password = app.config['DEVELOPER_PASSWORD']
            
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

    # 方管排布图生成API
    @app.route('/api/brb/tube-layout', methods=['POST'])
    def brb_tube_layout_api():
        try:
            import sys
            import os
            import io
            
            # 添加design目录到Python路径
            design_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'design')
            sys.path.insert(0, design_dir)
            
            from brb_tube_layout import TubeLayoutGenerator
            
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            project_name = data.get('projectName')
            parameter_tables = data.get('parameterTables')
            total_quantity = data.get('totalQuantity')
            strategy_config = data.get('strategyConfig')
            skip_plans_preview = bool(data.get('skipPlansPreview', False))

            if not project_name or not parameter_tables:
                return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
            
            # 创建生成器实例
            generator = TubeLayoutGenerator()

            # 快速模式：仅跑 strict_phased，省去并联多算法竞选（可通过请求体 tubeLayoutFast 或环境变量 BRB_TUBE_LAYOUT_FAST=1）
            import os as _os
            _fast_env = _os.environ.get('BRB_TUBE_LAYOUT_FAST', '').lower() in ('1', 'true', 'yes')
            if strategy_config is None and (bool(data.get('tubeLayoutFast')) or _fast_env):
                strategy_config = generator._get_fast_strategy_config()
            if _os.environ.get('BRB_TUBE_LAYOUT_SKIP_PREVIEW', '').lower() in ('1', 'true', 'yes'):
                skip_plans_preview = True
            
            # 生成方管排布图
            result = generator.generate_tube_layout(
                project_name,
                parameter_tables,
                strategy_config=strategy_config,
                skip_plans_preview=skip_plans_preview,
            )
            
            # 统一返回可下载文件信息，避免下载阶段重复触发生成
            upload_folder = app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            files_info = []

            if isinstance(result, tuple) and len(result) == 2:
                stream, filename = result
                safe_name = secure_filename(filename) or f'tube_layout_{uuid.uuid4().hex}.dxf'
                if not safe_name.lower().endswith('.dxf'):
                    safe_name = f'{safe_name}.dxf'
                stored_name = f'{uuid.uuid4().hex}_{safe_name}'
                stored_path = os.path.join(upload_folder, stored_name)

                stream.seek(0)
                with open(stored_path, 'wb') as f:
                    f.write(stream.read())

                files_info.append({
                    'name': filename,
                    'path': stored_path
                })
            elif isinstance(result, list):
                for item in result:
                    if isinstance(item, str):
                        files_info.append({
                            'name': os.path.basename(item),
                            'path': item
                        })

            return jsonify({'status': 'success', 'message': '方管排布图生成完成', 'result': files_info})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'生成方管排布图时出错: {str(e)}'}), 500

    # 解析 BRB 生产任务书 Excel
    @app.route('/api/brb/parse-taskbook', methods=['POST'])
    def brb_parse_taskbook_api():
        try:
            from parse_brb_taskbook import parse_brb_taskbook

            if 'file' not in request.files:
                return jsonify({'status': 'error', 'message': '未上传文件'}), 400

            file = request.files['file']
            if not file or not file.filename:
                return jsonify({'status': 'error', 'message': '文件名为空'}), 400

            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext not in ('xlsx', 'xlsm'):
                return jsonify({'status': 'error', 'message': '仅支持 .xlsx / .xlsm 任务书文件'}), 400

            upload_folder = app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            stored_name = f'{uuid.uuid4().hex}_taskbook.{ext}'
            stored_path = os.path.join(upload_folder, stored_name)
            file.save(stored_path)

            try:
                result = parse_brb_taskbook(stored_path)
            finally:
                try:
                    os.remove(stored_path)
                except OSError:
                    pass

            skipped = result.get('skippedNonBrb') or []
            msg = (
                f"已解析任务书「{result.get('projectName') or '未命名'}」："
                f"{result.get('forceGroupCount', 0)} 种屈服力，"
                f"{result.get('brbCount', 0)} 种规格，共 {result.get('totalQuantity', 0)} 件"
            )
            if skipped:
                msg += f"；已跳过非 BRB：{', '.join(skipped[:5])}"
                if len(skipped) > 5:
                    msg += f" 等 {len(skipped)} 项"

            return jsonify({
                'status': 'success',
                'message': msg,
                'result': result,
            })
        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'解析任务书失败: {str(e)}'}), 500
    
    # BRB连接件绘制API
    @app.route('/api/brb/connector-drawing', methods=['POST'])
    def brb_connector_drawing_api():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            project_name = data.get('projectName')
            parameter_tables = data.get('parameterTables')
            
            if not project_name or not parameter_tables:
                return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
            
            # 这里可以实现BRB连接件绘制的逻辑
            # 目前先返回一个成功的响应，后续可以根据实际需求实现具体的绘制功能
            
            # 模拟生成图纸的过程
            import io
            import tempfile
            
            # 创建一个简单的DXF文件作为示例
            dxf_content = f'''
999
DXF created by BRB Connector Drawing Tool
0
SECTION
2
HEADER
9
$ACADVER
1
AC1009
9
$EXTMIN
10
0.0
20
0.0
30
0.0
9
$EXTMAX
10
100.0
20
100.0
30
0.0
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
10
10.0
20
10.0
11
90.0
21
10.0
0
LINE
10
90.0
20
10.0
11
90.0
21
90.0
0
LINE
10
90.0
20
90.0
11
10.0
21
90.0
0
LINE
10
10.0
20
90.0
11
10.0
21
10.0
0
ENDSEC
0
EOF
'''
            
            # 创建内存流
            stream = io.BytesIO()
            stream.write(dxf_content.encode('utf-8'))
            stream.seek(0)
            
            filename = f'{project_name}_connector.dxf'
            
            return send_file(
                stream,
                as_attachment=True,
                download_name=filename,
                mimetype='application/dxf'
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'生成连接件图纸时出错: {str(e)}'}), 500

    # 文件下载API
    @app.route('/api/download/file', methods=['GET'])
    def download_file():
        try:
            # 获取文件路径参数
            file_path = request.args.get('path')
            if not file_path:
                return jsonify({'status': 'error', 'message': '缺少文件路径参数'}), 400
            
            # 检查是否是tube_layout文件
            if (file_path.startswith('_tube_layout_') or '_方管排布_' in file_path) and file_path.endswith('.dxf'):
                # 在tube_layout目录下查找文件
                tube_layout_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'design', 'data', 'tube_layout')
                abs_file_path = os.path.join(tube_layout_dir, file_path)
                is_safe = os.path.exists(abs_file_path)
            else:
                # 验证文件路径是否安全
                is_safe, abs_file_path = validate_file_path(file_path)
            
            if not is_safe:
                return jsonify({'status': 'error', 'message': '文件路径不安全'}), 403
            
            # 获取文件名
            filename = os.path.basename(abs_file_path)
            
            # 发送文件
            return send_file(abs_file_path, as_attachment=True, download_name=filename)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'下载过程出错: {str(e)}'}), 500

    # 批量文件下载API
    @app.route('/api/download/batch', methods=['POST'])
    def batch_download_files():
        try:
            import zipfile
            import re

            data = request.get_json() or {}
            # 优先 files: [{path, name}]，保留 filePaths 兼容旧前端
            files_payload = data.get('files')
            file_paths = data.get('filePaths', [])
            file_names = data.get('fileNames', [])

            entries = []
            if isinstance(files_payload, list) and files_payload:
                for item in files_payload:
                    if not isinstance(item, dict):
                        continue
                    path = item.get('path')
                    if not path:
                        continue
                    entries.append({
                        'path': path,
                        'name': item.get('name') or os.path.basename(path),
                    })
            elif isinstance(file_paths, list):
                for i, path in enumerate(file_paths):
                    display = file_names[i] if isinstance(file_names, list) and i < len(file_names) else None
                    entries.append({
                        'path': path,
                        'name': display or os.path.basename(path),
                    })

            if not entries:
                return jsonify({'status': 'error', 'message': '缺少有效的文件路径列表'}), 400

            project_root = app.config['PROJECT_ROOT']
            valid_entries = []
            for entry in entries:
                is_safe, abs_file_path = validate_file_path(entry['path'], project_root)
                if is_safe:
                    valid_entries.append({
                        'abs_path': abs_file_path,
                        'name': entry['name'],
                    })

            if not valid_entries:
                return jsonify({'status': 'error', 'message': '没有有效的文件可以下载'}), 404

            def _safe_zip_arcname(display_name, fallback_path):
                """保留中文显示名写入 ZIP；仅去掉路径分隔与非法控制字符。"""
                name = os.path.basename(str(display_name or '').strip()) or os.path.basename(fallback_path)
                name = name.replace('\\', '_').replace('/', '_').replace('\x00', '')
                name = re.sub(r'[\r\n\t]', ' ', name).strip(' .')
                if not name:
                    name = os.path.basename(fallback_path) or 'file'
                return name

            used_names = set()

            def _unique_arcname(name):
                if name not in used_names:
                    used_names.add(name)
                    return name
                base, ext = os.path.splitext(name)
                idx = 2
                while True:
                    candidate = f'{base}_{idx}{ext}'
                    if candidate not in used_names:
                        used_names.add(candidate)
                        return candidate
                    idx += 1

            with tempfile.NamedTemporaryFile(mode='w+b', suffix='.zip', delete=False) as temp_zip:
                with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for entry in valid_entries:
                        abs_path = entry['abs_path']
                        arcname = _unique_arcname(_safe_zip_arcname(entry['name'], abs_path))
                        # UTF-8 文件名标志，避免解压后中文乱码
                        info = zipfile.ZipInfo(filename=arcname)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        info.flag_bits |= 0x800
                        with open(abs_path, 'rb') as src:
                            zf.writestr(info, src.read())
                temp_zip_path = temp_zip.name

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
            
            # 检查是否是tube_layout文件
            if file_path.endswith('.dxf') and '_方管排布_' in file_path:
                # 在tube_layout目录下查找文件
                tube_layout_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'design', 'data', 'tube_layout')
                abs_file_path = os.path.join(tube_layout_dir, file_path)
                is_safe = os.path.exists(abs_file_path)
            else:
                # 验证文件路径是否安全
                is_safe, abs_file_path = validate_file_path(file_path)
            
            if not is_safe:
                return jsonify({'status': 'error', 'message': '文件路径不安全'}), 403
            
            # 删除文件
            os.remove(abs_file_path)
            
            return jsonify({'status': 'success', 'message': '文件删除成功'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'文件删除过程出错: {str(e)}'}), 500

    # 用户注册API
    @app.route('/api/auth/register', methods=['POST'])
    def register_api():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
            
            # 验证用户名和密码长度
            if len(username) < 2 or len(username) > 20:
                return jsonify({'status': 'error', 'message': '用户名长度必须在2-20个字符之间'}), 400
            
            if len(password) < 6:
                return jsonify({'status': 'error', 'message': '密码长度必须至少为6个字符'}), 400
            
            # 检查用户名是否已存在
            user_model = UserModel()
            existing_user_by_username = user_model.get_user_by_username(username)
            if existing_user_by_username:
                return jsonify({'status': 'error', 'message': '用户名已存在'}), 400
            
            # 生成密码哈希
            password_hash = get_password_hash(password)
            
            # 创建用户
            user_id = user_model.create_user(username, password_hash)
            
            # 创建访问令牌
            access_token = create_access_token(data={'sub': user_id, 'username': username})
            
            return jsonify({
                'status': 'success', 
                'message': '注册成功',
                'user': {
                    'id': user_id,
                    'username': username
                },
                'access_token': access_token
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'注册过程出错: {str(e)}'}), 500

    # 用户登录API
    @app.route('/api/auth/login', methods=['POST'])
    def login_api():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
            
            # 查找用户
            user_model = UserModel()
            user = user_model.get_user_by_username(username)
            
            if not user:
                return jsonify({'status': 'error', 'message': '用户名或密码错误'}), 401
            
            # 验证密码
            if not verify_password(password, user.get('password_hash')):
                return jsonify({'status': 'error', 'message': '用户名或密码错误'}), 401
            
            # 创建访问令牌
            user_id = user.get('id')
            access_token = create_access_token(data={'sub': user_id, 'username': username})
            
            return jsonify({
                'status': 'success', 
                'message': '登录成功',
                'user': {
                    'id': user_id,
                    'username': user.get('username')
                },
                'access_token': access_token
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'登录过程出错: {str(e)}'}), 500

    # 验证令牌API
    @app.route('/api/auth/verify', methods=['POST'])
    def verify_api():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            token = data.get('token')
            if not token:
                return jsonify({'status': 'error', 'message': '缺少令牌参数'}), 400
            
            # 解码令牌
            payload = decode_access_token(token)
            if not payload:
                return jsonify({'status': 'error', 'message': '无效的令牌'}), 401
            
            # 获取用户信息
            user_id = payload.get('sub')
            user_model = UserModel()
            user = user_model.get_user_by_id(user_id)
            
            if not user:
                return jsonify({'status': 'error', 'message': '用户不存在'}), 401
            
            return jsonify({
                'status': 'success', 
                'message': '令牌验证成功',
                'user': {
                    'id': user.get('id'),
                    'username': user.get('username')
                }
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'验证过程出错: {str(e)}'}), 500

    # 获取用户列表API
    @app.route('/api/admin/users', methods=['GET'])
    def get_users_api():
        try:
            user_model = UserModel()
            users = []
            for user_id, user_data in user_model.users.items():
                users.append({
                    'id': user_data.get('id'),
                    'username': user_data.get('username'),
                    'role': user_data.get('role'),
                    'permissions': user_data.get('permissions', []),
                    'created_at': user_data.get('created_at')
                })
            return jsonify({'status': 'success', 'message': '获取用户列表成功', 'users': users})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'获取用户列表出错: {str(e)}'}), 500

    # 获取用户权限API
    @app.route('/api/admin/users/<user_id>/permissions', methods=['GET'])
    def get_user_permissions_api(user_id):
        try:
            user_model = UserModel()
            permissions = user_model.get_user_permissions(user_id)
            return jsonify({'status': 'success', 'message': '获取用户权限成功', 'permissions': permissions})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'获取用户权限出错: {str(e)}'}), 500

    # 添加用户权限API
    @app.route('/api/admin/users/<user_id>/permissions', methods=['POST'])
    def add_user_permission_api(user_id):
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            permission = data.get('permission')
            if not permission:
                return jsonify({'status': 'error', 'message': '缺少权限参数'}), 400
            
            user_model = UserModel()
            success = user_model.add_user_permission(user_id, permission)
            if success:
                return jsonify({'status': 'success', 'message': '添加用户权限成功'})
            else:
                return jsonify({'status': 'error', 'message': '添加用户权限失败'}), 400
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'添加用户权限出错: {str(e)}'}), 500

    # 移除用户权限API
    @app.route('/api/admin/users/<user_id>/permissions/<permission>', methods=['DELETE'])
    def remove_user_permission_api(user_id, permission):
        try:
            user_model = UserModel()
            success = user_model.remove_user_permission(user_id, permission)
            if success:
                return jsonify({'status': 'success', 'message': '移除用户权限成功'})
            else:
                return jsonify({'status': 'error', 'message': '移除用户权限失败'}), 400
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'移除用户权限出错: {str(e)}'}), 500

    # 设置用户权限API
    @app.route('/api/admin/users/<user_id>/permissions', methods=['PUT'])
    def set_user_permissions_api(user_id):
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            permissions = data.get('permissions')
            if not isinstance(permissions, list):
                return jsonify({'status': 'error', 'message': '权限参数必须是数组'}), 400
            
            user_model = UserModel()
            success = user_model.set_user_permissions(user_id, permissions)
            if success:
                return jsonify({'status': 'success', 'message': '设置用户权限成功'})
            else:
                return jsonify({'status': 'error', 'message': '设置用户权限失败'}), 400
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'设置用户权限出错: {str(e)}'}), 500

    # 检查用户权限API
    @app.route('/api/auth/check-permission', methods=['POST'])
    def check_permission_api():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            token = data.get('token')
            permission = data.get('permission')
            
            if not token or not permission:
                return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
            
            # 解码令牌
            payload = decode_access_token(token)
            if not payload:
                return jsonify({'status': 'error', 'message': '无效的令牌'}), 401
            
            # 检查权限
            user_id = payload.get('sub')
            user_model = UserModel()
            has_perm = user_model.has_permission(user_id, permission)
            
            return jsonify({
                'status': 'success', 
                'message': '检查权限成功',
                'has_permission': has_perm
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'检查权限出错: {str(e)}'}), 500

    # 修改密码API
    @app.route('/api/auth/change-password', methods=['POST'])
    def change_password_api():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            
            if not current_password or not new_password:
                return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400
            
            # 从请求头获取令牌
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'status': 'error', 'message': '缺少认证令牌'}), 401
            
            # 提取令牌
            token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
            
            # 解码令牌
            payload = decode_access_token(token)
            if not payload:
                return jsonify({'status': 'error', 'message': '无效的令牌'}), 401
            
            # 获取用户ID
            user_id = payload.get('sub')
            user_model = UserModel()
            user = user_model.get_user_by_id(user_id)
            
            if not user:
                return jsonify({'status': 'error', 'message': '用户不存在'}), 404
            
            # 验证当前密码
            if not verify_password(current_password, user.get('password_hash')):
                return jsonify({'status': 'error', 'message': '当前密码错误'}), 400
            
            # 生成新密码的哈希值
            new_password_hash = get_password_hash(new_password)
            
            # 更新用户密码
            user_model.update_user(user_id, {'password_hash': new_password_hash})
            
            return jsonify({
                'status': 'success', 
                'message': '密码修改成功'
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'修改密码出错: {str(e)}'}), 500

    # 试验文件API - 获取文件列表
    @app.route('/api/test-files/list', methods=['GET'])
    def get_test_files_list():
        try:
            # 网络路径
            network_path = Config.get_test_files_network_path()
            
            # 检查路径是否存在
            if not os.path.exists(network_path):
                return jsonify({'status': 'error', 'message': f'无法访问网络路径: {network_path}'}), 404
            
            # 获取文件列表
            files = []
            for item in os.listdir(network_path):
                item_path = os.path.join(network_path, item)
                if os.path.isfile(item_path):
                    # 获取文件信息
                    stat = os.stat(item_path)
                    files.append({
                        'name': item,
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'type': os.path.splitext(item)[1].lower()
                    })
            
            # 按修改时间排序（最新的在前）
            files.sort(key=lambda x: x['modified'], reverse=True)
            
            return jsonify({
                'status': 'success',
                'files': files,
                'path': network_path
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'获取文件列表出错: {str(e)}'}), 500

    # 试验文件API - 下载文件
    @app.route('/api/test-files/download', methods=['POST'])
    def download_test_file():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            filepath = data.get('filepath') or data.get('filename')
            if not filepath:
                return jsonify({'status': 'error', 'message': '缺少文件路径'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            file_path = os.path.join(network_path, filepath)
            
            # 安全检查：确保路径在基础路径内
            real_base_path = os.path.realpath(network_path)
            real_file_path = os.path.realpath(file_path)
            if not real_file_path.startswith(real_base_path):
                return jsonify({'status': 'error', 'message': '非法路径访问'}), 403
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return jsonify({'status': 'error', 'message': '文件不存在'}), 404
            
            # 检查是否为文件（防止目录遍历攻击）
            if not os.path.isfile(file_path):
                return jsonify({'status': 'error', 'message': '不是有效的文件'}), 400
            
            # 获取文件名（用于下载）
            download_name = os.path.basename(file_path)
            
            return send_file(file_path, as_attachment=True, download_name=download_name)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'下载文件出错: {str(e)}'}), 500

    # 试验文件API - 上传文件
    @app.route('/api/test-files/upload', methods=['POST'])
    def upload_test_file():
        try:
            # 检查是否有文件
            if 'file' not in request.files:
                return jsonify({'status': 'error', 'message': '未找到上传文件'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'status': 'error', 'message': '未选择文件'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            
            # 获取当前路径参数
            current_path = request.form.get('current_path', '')
            
            # 构建目标路径
            if current_path:
                target_dir = os.path.join(network_path, current_path)
            else:
                target_dir = network_path
            
            # 检查路径是否存在
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            # 获取原始文件名
            filename = file.filename
            if not filename:
                return jsonify({'status': 'error', 'message': '无效的文件名'}), 400
            
            # 安全检查：防止路径遍历攻击
            if '..' in filename or '/' in filename or '\\' in filename:
                return jsonify({'status': 'error', 'message': '文件名包含非法字符'}), 400
            
            # 保存文件
            file_path = os.path.join(target_dir, filename)
            file.save(file_path)
            
            return jsonify({
                'status': 'success',
                'message': '文件上传成功',
                'filename': filename
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'上传文件出错: {str(e)}'}), 500

    # 试验文件API - 上传文件夹
    @app.route('/api/test-files/upload-folder', methods=['POST'])
    def upload_test_folder():
        try:
            # 检查是否有文件
            if 'file' not in request.files:
                return jsonify({'status': 'error', 'message': '未找到上传文件'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'status': 'error', 'message': '未选择文件'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            
            # 获取相对路径和当前路径参数
            relative_path = request.form.get('relative_path', '')
            current_path = request.form.get('current_path', '')
            
            if not relative_path:
                return jsonify({'status': 'error', 'message': '缺少相对路径信息'}), 400
            
            # 安全检查：防止路径遍历攻击
            if '..' in relative_path:
                return jsonify({'status': 'error', 'message': '路径包含非法字符'}), 400
            
            # 构建目标路径
            if current_path:
                target_path = os.path.join(network_path, current_path, relative_path)
            else:
                target_path = os.path.join(network_path, relative_path)
            
            # 安全检查：确保路径在基础路径内
            real_base_path = os.path.realpath(network_path)
            real_target_path = os.path.realpath(target_path)
            if not real_target_path.startswith(real_base_path):
                return jsonify({'status': 'error', 'message': '非法路径访问'}), 403
            
            # 创建目标目录
            target_dir = os.path.dirname(target_path)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            # 保存文件
            file.save(target_path)
            
            return jsonify({
                'status': 'success',
                'message': '文件上传成功',
                'path': relative_path
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'上传文件出错: {str(e)}'}), 500

    # 试验文件API - 下载文件夹（打包为ZIP）
    @app.route('/api/test-files/download-directory', methods=['POST'])
    def download_test_directory():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            dirpath = data.get('dirpath')
            if not dirpath:
                return jsonify({'status': 'error', 'message': '缺少文件夹路径'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            dir_path = os.path.join(network_path, dirpath)
            
            # 安全检查：确保路径在基础路径内
            real_base_path = os.path.realpath(network_path)
            real_dir_path = os.path.realpath(dir_path)
            if not real_dir_path.startswith(real_base_path):
                return jsonify({'status': 'error', 'message': '非法路径访问'}), 403
            
            # 检查文件夹是否存在
            if not os.path.exists(dir_path):
                return jsonify({'status': 'error', 'message': '文件夹不存在'}), 404
            
            # 检查是否为文件夹
            if not os.path.isdir(dir_path):
                return jsonify({'status': 'error', 'message': '不是有效的文件夹'}), 400
            
            # 创建临时ZIP文件
            import tempfile
            import shutil
            
            temp_dir = tempfile.gettempdir()
            folder_name = os.path.basename(dir_path)
            zip_path = os.path.join(temp_dir, f"{folder_name}.zip")
            
            # 删除已存在的临时ZIP文件
            if os.path.exists(zip_path):
                os.remove(zip_path)
            
            # 创建ZIP文件
            shutil.make_archive(
                os.path.join(temp_dir, folder_name),
                'zip',
                os.path.dirname(dir_path),
                folder_name
            )
            
            return send_file(zip_path, as_attachment=True, download_name=f"{folder_name}.zip")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'下载文件夹出错: {str(e)}'}), 500

    # 试验文件API - 读取文件内容
    @app.route('/api/test-files/read', methods=['POST'])
    def read_test_file():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            filepath = data.get('filepath') or data.get('filename')
            if not filepath:
                return jsonify({'status': 'error', 'message': '缺少文件路径'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            file_path = os.path.join(network_path, filepath)
            
            # 安全检查：确保路径在基础路径内
            real_base_path = os.path.realpath(network_path)
            real_file_path = os.path.realpath(file_path)
            if not real_file_path.startswith(real_base_path):
                return jsonify({'status': 'error', 'message': '非法路径访问'}), 403
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return jsonify({'status': 'error', 'message': '文件不存在'}), 404
            
            # 检查是否为文件
            if not os.path.isfile(file_path):
                return jsonify({'status': 'error', 'message': '不是有效的文件'}), 400
            
            # 获取文件名
            filename = os.path.basename(file_path)
            
            # 尝试读取文件内容
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return jsonify({
                    'status': 'success',
                    'content': content,
                    'filename': filename
                })
            except UnicodeDecodeError:
                # 如果UTF-8解码失败，尝试其他编码
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        content = f.read()
                    return jsonify({
                        'status': 'success',
                        'content': content,
                        'filename': filename
                    })
                except:
                    return jsonify({'status': 'error', 'message': '无法读取文件内容，可能不是文本文件'}), 400
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'读取文件出错: {str(e)}'}), 500

    # 试验文件API - 保存文件内容
    @app.route('/api/test-files/save', methods=['POST'])
    def save_test_file():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            filepath = data.get('filepath') or data.get('filename')
            content = data.get('content')
            
            if not filepath:
                return jsonify({'status': 'error', 'message': '缺少文件路径'}), 400
            
            if content is None:
                return jsonify({'status': 'error', 'message': '缺少文件内容'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            file_path = os.path.join(network_path, filepath)
            
            # 安全检查：确保路径在基础路径内
            real_base_path = os.path.realpath(network_path)
            real_file_path = os.path.realpath(file_path)
            if not real_file_path.startswith(real_base_path):
                return jsonify({'status': 'error', 'message': '非法路径访问'}), 403
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return jsonify({'status': 'error', 'message': '文件不存在'}), 404
            
            # 检查是否为文件
            if not os.path.isfile(file_path):
                return jsonify({'status': 'error', 'message': '不是有效的文件'}), 400
            
            # 保存文件内容
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return jsonify({
                'status': 'success',
                'message': '文件保存成功',
                'filename': os.path.basename(filepath)
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'保存文件出错: {str(e)}'}), 500

    # 试验文件API - 导出Excel文件（使用openpyxl）
    @app.route('/api/test-files/export-excel', methods=['POST'])
    def export_excel_file():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            filename = data.get('filename')
            sheets_data = data.get('sheets')
            
            if not filename:
                return jsonify({'status': 'error', 'message': '缺少文件名'}), 400
            
            if not sheets_data:
                return jsonify({'status': 'error', 'message': '缺少工作表数据'}), 400
            
            # 使用openpyxl创建Excel文件
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
            from openpyxl.utils import get_column_letter
            
            # 辅助函数：确保颜色是有效的aRGB格式
            def ensure_argb_color(color):
                if not color:
                    return 'FF000000'  # 默认黑色
                # 移除#号
                color = color.replace('#', '')
                # 如果是6位RGB，添加FF前缀
                if len(color) == 6:
                    return 'FF' + color
                # 如果已经是8位aRGB，直接返回
                if len(color) == 8:
                    return color
                # 其他情况返回默认黑色
                return 'FF000000'
            
            wb = Workbook()
            # 删除默认工作表
            wb.remove(wb.active)
            
            for sheet_data in sheets_data:
                sheet_name = sheet_data.get('name', 'Sheet1')
                ws = wb.create_sheet(title=sheet_name)
                
                celldata = sheet_data.get('celldata', [])
                config = sheet_data.get('config', {})
                
                # 打印调试信息
                print(f"工作表: {sheet_name}")
                print(f"单元格数量: {len(celldata)}")
                if len(celldata) > 0:
                    print(f"第一个单元格数据示例: {celldata[0]}")
                
                # 填充单元格数据和样式
                for cell in celldata:
                    row = cell.get('r', 0) + 1  # openpyxl行号从1开始
                    col = cell.get('c', 0) + 1  # openpyxl列号从1开始
                    cell_v = cell.get('v', {})
                    
                    # 设置单元格值
                    if 'v' in cell_v:
                        ws.cell(row=row, column=col, value=cell_v['v'])
                    
                    # 设置背景色
                    if 'bg' in cell_v:
                        bg_color = ensure_argb_color(cell_v['bg'])
                        ws.cell(row=row, column=col).fill = PatternFill(
                            start_color=bg_color,
                            end_color=bg_color,
                            fill_type='solid'
                        )
                    
                    # 设置字体颜色
                    font_props = {}
                    if 'fc' in cell_v:
                        font_props['color'] = ensure_argb_color(cell_v['fc'])
                    if 'fs' in cell_v:
                        font_props['size'] = cell_v['fs']
                    if 'bl' in cell_v and cell_v['bl'] == 1:
                        font_props['bold'] = True
                    if font_props:
                        ws.cell(row=row, column=col).font = Font(**font_props)
                    
                    # 设置对齐
                    align_props = {}
                    if 'ht' in cell_v:
                        # 0=left, 1=center, 2=right
                        align_props['horizontal'] = ['left', 'center', 'right'][cell_v['ht']]
                    if 'vt' in cell_v:
                        # 0=top, 1=middle, 2=bottom
                        align_props['vertical'] = ['top', 'center', 'bottom'][cell_v['vt']]
                    if align_props:
                        ws.cell(row=row, column=col).alignment = Alignment(**align_props)
                
                # 设置列宽
                # Luckysheet的列宽单位是像素，openpyxl的单位是字符宽度
                # LuckyExcel导入时的转换公式：pixel = (excel_width - 0.83) * 8 + 5
                # 反向计算：excel_width = (pixel - 5) / 8 + 0.83
                if 'columnlen' in config:
                    for col_str, width in config['columnlen'].items():
                        col = int(col_str) + 1
                        # 使用与LuckyExcel导入时相反的转换公式
                        char_width = (width - 5) / 8 + 0.83
                        # 设置最小宽度为8，避免列太窄
                        ws.column_dimensions[get_column_letter(col)].width = max(char_width, 8)
                
                # 设置行高
                # LuckyExcel导入时的转换公式：pixel = Math.round(rowHeight / (72/96))
                # 反向计算：rowHeight = pixel * (72/96) = pixel * 0.75
                if 'rowlen' in config:
                    for row_str, height in config['rowlen'].items():
                        row = int(row_str) + 1
                        # 使用与LuckyExcel导入时相反的转换公式
                        excel_height = height * 0.75
                        ws.row_dimensions[row].height = excel_height
                
                # 设置合并单元格
                if 'merge' in config:
                    for merge_key, merge_data in config['merge'].items():
                        start_row = merge_data['r'] + 1
                        start_col = merge_data['c'] + 1
                        end_row = start_row + merge_data.get('rs', 1) - 1
                        end_col = start_col + merge_data.get('cs', 1) - 1
                        ws.merge_cells(start_row=start_row, start_column=start_col, 
                                      end_row=end_row, end_column=end_col)
                
                # 处理边框信息 (Luckysheet的边框存储在config.borderInfo中)
                # 这是主要的边框处理方式
                if 'borderInfo' in config:
                    border_info = config['borderInfo']
                    print(f"处理边框信息: {border_info}")
                    print(f"边框信息数量: {len(border_info)}")
                    
                    for border_item in border_info:
                        border_type = border_item.get('rangeType')
                        border_style_data = border_item.get('style')
                        border_color = ensure_argb_color(border_item.get('color', '#000000'))
                        
                        # 创建边框样式
                        side_style = Side(style='thin', color=border_color)
                        
                        if border_type == 'range':
                            # 范围边框
                            range_data = border_item.get('range', [])
                            for range_item in range_data:
                                start_row = range_item.get('row', [0, 0])[0] + 1
                                end_row = range_item.get('row', [0, 0])[1] + 1
                                start_col = range_item.get('column', [0, 0])[0] + 1
                                end_col = range_item.get('column', [0, 0])[1] + 1
                                
                                border_type_name = border_item.get('borderType')
                                
                                for r in range(start_row, end_row + 1):
                                    for c in range(start_col, end_col + 1):
                                        cell = ws.cell(row=r, column=c)
                                        current_border = cell.border or Border()
                                        
                                        new_border = {}
                                        if hasattr(current_border, 'top') and current_border.top.style:
                                            new_border['top'] = current_border.top
                                        if hasattr(current_border, 'bottom') and current_border.bottom.style:
                                            new_border['bottom'] = current_border.bottom
                                        if hasattr(current_border, 'left') and current_border.left.style:
                                            new_border['left'] = current_border.left
                                        if hasattr(current_border, 'right') and current_border.right.style:
                                            new_border['right'] = current_border.right
                                        
                                        if border_type_name in ['border-all', 'border-outside', 'border-top']:
                                            new_border['top'] = side_style
                                        if border_type_name in ['border-all', 'border-outside', 'border-bottom']:
                                            new_border['bottom'] = side_style
                                        if border_type_name in ['border-all', 'border-outside', 'border-left']:
                                            new_border['left'] = side_style
                                        if border_type_name in ['border-all', 'border-outside', 'border-right']:
                                            new_border['right'] = side_style
                                        
                                        if new_border:
                                            cell.border = Border(**new_border)
                        
                        elif border_type == 'cell':
                            # 单元格边框
                            cell_value = border_item.get('value', {})
                            row = cell_value.get('row_index', 0) + 1
                            col = cell_value.get('col_index', 0) + 1
                            
                            cell = ws.cell(row=row, column=col)
                            
                            # 构建边框
                            new_border = {}
                            
                            # 左边框
                            if 'l' in cell_value:
                                l_style = cell_value['l'].get('style', 1)
                                l_color = ensure_argb_color(cell_value['l'].get('color', '#000000'))
                                new_border['left'] = Side(style='thin', color=l_color)
                            
                            # 右边框
                            if 'r' in cell_value:
                                r_style = cell_value['r'].get('style', 1)
                                r_color = ensure_argb_color(cell_value['r'].get('color', '#000000'))
                                new_border['right'] = Side(style='thin', color=r_color)
                            
                            # 上边框
                            if 't' in cell_value:
                                t_style = cell_value['t'].get('style', 1)
                                t_color = ensure_argb_color(cell_value['t'].get('color', '#000000'))
                                new_border['top'] = Side(style='thin', color=t_color)
                            
                            # 下边框
                            if 'b' in cell_value:
                                b_style = cell_value['b'].get('style', 1)
                                b_color = ensure_argb_color(cell_value['b'].get('color', '#000000'))
                                new_border['bottom'] = Side(style='thin', color=b_color)
                            
                            if new_border:
                                cell.border = Border(**new_border)
            
            # 保存到临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                wb.save(tmp.name)
                tmp_path = tmp.name
            
            # 读取临时文件并上传到网络路径
            network_path = Config.get_test_files_network_path()
            file_path = os.path.join(network_path, filename)
            
            # 复制文件到网络路径
            import shutil
            shutil.copy2(tmp_path, file_path)
            
            # 删除临时文件
            os.unlink(tmp_path)
            
            return jsonify({
                'status': 'success',
                'message': 'Excel文件导出成功',
                'filename': filename
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'导出Excel文件出错: {str(e)}'}), 500

    # 试验文件API - 读取Word文件
    @app.route('/api/test-files/read-word', methods=['POST'])
    def read_word_file():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            filepath = data.get('filepath') or data.get('filename')
            if not filepath:
                return jsonify({'status': 'error', 'message': '缺少文件路径'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            file_path = os.path.join(network_path, filepath)
            
            # 安全检查
            real_base_path = os.path.realpath(network_path)
            real_file_path = os.path.realpath(file_path)
            if not real_file_path.startswith(real_base_path):
                return jsonify({'status': 'error', 'message': '非法路径访问'}), 403
            
            print(f"读取Word文件: {file_path}")
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return jsonify({'status': 'error', 'message': '文件不存在'}), 404
            
            # 检查是否为文件
            if not os.path.isfile(file_path):
                return jsonify({'status': 'error', 'message': '不是有效的文件'}), 400
            
            from docx import Document
            import mammoth
            import zipfile
            import io
            
            html = ''
            
            # 获取文件扩展名
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 检查文件是否是ZIP格式（docx实际上是ZIP格式）
            is_docx = False
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(4)
                    if header[:4] == b'PK\x03\x04':
                        is_docx = True
                        print("检测到文件是ZIP格式（docx）")
            except:
                pass
            
            # 如果是docx格式，尝试读取
            if is_docx or file_ext == '.docx':
                try:
                    with open(file_path, 'rb') as docx_file:
                        result = mammoth.convert_to_html(docx_file)
                        html = result.value
                        print(f"mammoth转换成功")
                except Exception as mammoth_error:
                    print(f"mammoth转换失败: {mammoth_error}")
                    
                    try:
                        doc = Document(file_path)
                        html_parts = []
                        
                        for para in doc.paragraphs:
                            text = para.text
                            if text.strip():
                                style_name = para.style.name if para.style else ''
                                if 'Heading 1' in style_name:
                                    html_parts.append(f'<h1>{text}</h1>')
                                elif 'Heading 2' in style_name:
                                    html_parts.append(f'<h2>{text}</h2>')
                                elif 'Heading 3' in style_name:
                                    html_parts.append(f'<h3>{text}</h3>')
                                else:
                                    html_parts.append(f'<p>{text}</p>')
                        
                        for table in doc.tables:
                            html_table = '<table border="1" style="border-collapse: collapse;">'
                            for row in table.rows:
                                html_table += '<tr>'
                                for cell in row.cells:
                                    html_table += f'<td>{cell.text}</td>'
                                html_table += '</tr>'
                            html_table += '</table>'
                            html_parts.append(html_table)
                        
                        html = ''.join(html_parts)
                        print(f"python-docx读取成功")
                    except Exception as docx_error:
                        print(f"python-docx读取失败: {docx_error}")
                        return jsonify({'status': 'error', 'message': f'无法读取Word文件: {str(docx_error)}'}), 500
            elif file_ext == '.doc':
                # 处理旧版 .doc 格式
                print("检测到旧版 .doc 格式文件")
                
                # 方法1: 尝试使用 win32com (Windows 环境) - 最可靠
                try:
                    import win32com.client
                    
                    word = None
                    doc = None
                    try:
                        word = win32com.client.Dispatch("Word.Application")
                        word.Visible = False
                        doc = word.Documents.Open(os.path.abspath(file_path))
                        
                        # 获取文档内容
                        text_content = doc.Content.Text
                        
                        # 将文本转换为HTML段落
                        paragraphs = text_content.split('\r')
                        html_parts = []
                        for para in paragraphs:
                            if para.strip():
                                html_parts.append(f'<p>{para}</p>')
                        html = ''.join(html_parts)
                        
                        print(f"win32com 读取 .doc 文件成功")
                    finally:
                        if doc:
                            doc.Close(False)
                        if word:
                            word.Quit()
                except ImportError:
                    print("win32com (pywin32) 未安装，尝试其他方法")
                except Exception as win32_error:
                    print(f"win32com 读取失败: {win32_error}")
                
                # 方法2: 尝试使用 docx2txt
                if not html:
                    try:
                        import docx2txt
                        text_content = docx2txt.process(file_path)
                        if text_content:
                            paragraphs = text_content.split('\n')
                            html_parts = []
                            for para in paragraphs:
                                if para.strip():
                                    html_parts.append(f'<p>{para}</p>')
                            html = ''.join(html_parts)
                            print("docx2txt 读取 .doc 文件成功")
                    except ImportError:
                        print("docx2txt 未安装，尝试其他方法")
                    except Exception as docx2txt_error:
                        print(f"docx2txt 读取失败: {docx2txt_error}")
                
                # 方法3: 如果前两种方法失败，尝试使用 antiword
                if not html:
                    try:
                        import subprocess
                        result = subprocess.run(
                            ['antiword', file_path],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            text_content = result.stdout
                            paragraphs = text_content.split('\n')
                            html_parts = []
                            for para in paragraphs:
                                if para.strip():
                                    html_parts.append(f'<p>{para}</p>')
                            html = ''.join(html_parts)
                            print("antiword 读取 .doc 文件成功")
                    except FileNotFoundError:
                        print("antiword 未安装")
                    except Exception as antiword_error:
                        print(f"antiword 读取失败: {antiword_error}")
                
                # 方法4: 尝试使用 textract
                if not html:
                    try:
                        import textract
                        text_content = textract.process(file_path).decode('utf-8')
                        paragraphs = text_content.split('\n')
                        html_parts = []
                        for para in paragraphs:
                            if para.strip():
                                html_parts.append(f'<p>{para}</p>')
                        html = ''.join(html_parts)
                        print("textract 读取 .doc 文件成功")
                    except ImportError:
                        print("textract 未安装")
                    except Exception as textract_error:
                        print(f"textract 读取失败: {textract_error}")
                
                # 方法5: 尝试使用 olefile 读取 OLE 复合文档
                if not html:
                    try:
                        import olefile
                        ole = olefile.OleFileIO(file_path)
                        if ole.exists('WordDocument'):
                            stream = ole.openstream('WordDocument')
                            data = stream.read()
                            text = data.decode('utf-16-le', errors='ignore')
                            import re
                            text = re.sub(r'[^\x20-\x7E\u4e00-\u9fff\r\n]', '', text)
                            paragraphs = text.split('\n')
                            html_parts = []
                            for para in paragraphs:
                                if para.strip():
                                    html_parts.append(f'<p>{para.strip()}</p>')
                            html = ''.join(html_parts)
                            print("olefile 读取 .doc 文件成功")
                        ole.close()
                    except ImportError:
                        print("olefile 未安装")
                    except Exception as ole_error:
                        print(f"olefile 读取失败: {ole_error}")
                
                if not html:
                    return jsonify({
                        'status': 'error',
                        'message': '无法读取 .doc 格式文件。请确保已安装 pywin32 (pip install pywin32) 或 docx2txt (pip install docx2txt)，或将文件转换为 .docx 格式'
                    }), 400
            else:
                return jsonify({'status': 'error', 'message': f'不支持的文件格式: {file_ext}'}), 400
            
            if not html or not html.strip():
                html = '<p></p>'
            
            return jsonify({
                'status': 'success',
                'content': html,
                'filename': os.path.basename(filepath)
            })
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'读取Word文件出错: {str(e)}'}), 500

    # 试验文件API - 导出Word文件
    @app.route('/api/test-files/export-word', methods=['POST'])
    def export_word_file():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            filepath = data.get('filepath') or data.get('filename')
            html_content = data.get('content')
            
            if not filepath:
                return jsonify({'status': 'error', 'message': '缺少文件路径'}), 400
            
            if not html_content:
                return jsonify({'status': 'error', 'message': '缺少内容'}), 400
            
            # 使用python-docx创建Word文档
            from docx import Document
            from docx.shared import Pt, Inches, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from bs4 import BeautifulSoup
            
            doc = Document()
            
            # 解析HTML内容
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 遍历HTML元素并转换为Word格式
            for element in soup.descendants:
                if element is None or not hasattr(element, 'name') or element.name is None:
                    continue
                
                if element.name == 'p':
                    p = doc.add_paragraph()
                    text = element.get_text()
                    if text.strip():
                        run = p.add_run(text)
                        if element.get('style'):
                            style = element.get('style')
                            if 'bold' in style or 'font-weight: bold' in style:
                                run.bold = True
                            if 'italic' in style or 'font-style: italic' in style:
                                run.italic = True
                
                elif element.name == 'h1':
                    p = doc.add_heading(element.get_text(), level=1)
                
                elif element.name == 'h2':
                    p = doc.add_heading(element.get_text(), level=2)
                
                elif element.name == 'h3':
                    p = doc.add_heading(element.get_text(), level=3)
                
                elif element.name == 'ul':
                    for li in element.find_all('li', recursive=False):
                        doc.add_paragraph(li.get_text(), style='List Bullet')
                
                elif element.name == 'ol':
                    for li in element.find_all('li', recursive=False):
                        doc.add_paragraph(li.get_text(), style='List Number')
                
                elif element.name == 'table':
                    rows = element.find_all('tr')
                    if rows:
                        cols = len(rows[0].find_all(['td', 'th']))
                        table = doc.add_table(rows=len(rows), cols=cols)
                        table.style = 'Table Grid'
                        
                        for i, row in enumerate(rows):
                            cells = row.find_all(['td', 'th'])
                            for j, cell in enumerate(cells):
                                table.rows[i].cells[j].text = cell.get_text()
                
                elif element.name == 'br':
                    doc.add_paragraph()
            
            # 保存到临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                doc.save(tmp.name)
                tmp_path = tmp.name
            
            # 复制文件到网络路径
            network_path = Config.get_test_files_network_path()
            file_path = os.path.join(network_path, filepath)
            
            # 安全检查
            real_base_path = os.path.realpath(network_path)
            real_file_path = os.path.realpath(file_path)
            if not real_file_path.startswith(real_base_path):
                os.unlink(tmp_path)
                return jsonify({'status': 'error', 'message': '非法路径访问'}), 403
            
            # 确保目标目录存在
            target_dir = os.path.dirname(file_path)
            if target_dir and not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            import shutil
            shutil.copy2(tmp_path, file_path)
            
            # 删除临时文件
            os.unlink(tmp_path)
            
            return jsonify({
                'status': 'success',
                'message': 'Word文件导出成功',
                'filename': os.path.basename(filepath)
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'导出Word文件出错: {str(e)}'}), 500

    # 试验文件API - 删除单个文件（移动到回收站）
    @app.route('/api/test-files/delete', methods=['POST'])
    def delete_test_file():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            filepath = data.get('filepath') or data.get('filename')
            if not filepath:
                return jsonify({'status': 'error', 'message': '缺少文件路径'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            recycle_bin_path = os.path.join(network_path, '回收站')
            file_path = os.path.join(network_path, filepath)
            
            # 安全检查：确保路径在基础路径内
            real_base_path = os.path.realpath(network_path)
            real_file_path = os.path.realpath(file_path)
            if not real_file_path.startswith(real_base_path):
                return jsonify({'status': 'error', 'message': '非法路径访问'}), 403
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return jsonify({'status': 'error', 'message': '文件不存在'}), 404
            
            # 检查是否为文件
            if not os.path.isfile(file_path):
                return jsonify({'status': 'error', 'message': '不是有效的文件'}), 400
            
            # 创建回收站目录（如果不存在）
            if not os.path.exists(recycle_bin_path):
                os.makedirs(recycle_bin_path)
            
            # 生成回收站中的文件名（添加时间戳避免重名）
            import time
            timestamp = int(time.time())
            filename = os.path.basename(filepath)
            base_name, ext = os.path.splitext(filename)
            recycle_filename = f"{base_name}_{timestamp}{ext}"
            recycle_file_path = os.path.join(recycle_bin_path, recycle_filename)
            
            # 移动文件到回收站
            import shutil
            shutil.move(file_path, recycle_file_path)
            
            return jsonify({
                'status': 'success',
                'message': '文件已移至回收站',
                'filename': filename,
                'recycle_filename': recycle_filename
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'删除文件出错: {str(e)}'}), 500

    # 试验文件API - 批量删除文件（移动到回收站）
    @app.route('/api/test-files/batch-delete', methods=['POST'])
    def batch_delete_test_files():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            filenames = data.get('filenames')
            if not filenames or not isinstance(filenames, list):
                return jsonify({'status': 'error', 'message': '缺少文件名列表'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            recycle_bin_path = os.path.join(network_path, '回收站')
            
            # 创建回收站目录（如果不存在）
            if not os.path.exists(recycle_bin_path):
                os.makedirs(recycle_bin_path)
            
            import time
            import shutil
            
            deleted_count = 0
            failed_files = []
            
            for filename in filenames:
                file_path = os.path.join(network_path, filename)
                
                try:
                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        # 生成回收站中的文件名
                        timestamp = int(time.time())
                        base_name, ext = os.path.splitext(filename)
                        recycle_filename = f"{base_name}_{timestamp}{ext}"
                        recycle_file_path = os.path.join(recycle_bin_path, recycle_filename)
                        
                        # 移动文件到回收站
                        shutil.move(file_path, recycle_file_path)
                        deleted_count += 1
                    else:
                        failed_files.append(filename)
                except Exception as e:
                    print(f"删除文件 {filename} 失败: {e}")
                    failed_files.append(filename)
            
            if failed_files:
                return jsonify({
                    'status': 'partial',
                    'message': f'成功删除 {deleted_count} 个文件，{len(failed_files)} 个文件删除失败',
                    'deleted_count': deleted_count,
                    'failed_files': failed_files
                })
            
            return jsonify({
                'status': 'success',
                'message': f'成功删除 {deleted_count} 个文件',
                'deleted_count': deleted_count
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'批量删除文件出错: {str(e)}'}), 500

    # 试验文件API - 获取回收站文件列表
    @app.route('/api/test-files/recycle-bin', methods=['GET'])
    def get_recycle_bin_files():
        try:
            # 网络路径
            network_path = Config.get_test_files_network_path()
            recycle_bin_path = os.path.join(network_path, '回收站')
            
            # 如果回收站不存在，返回空列表
            if not os.path.exists(recycle_bin_path):
                return jsonify({
                    'status': 'success',
                    'files': [],
                    'network_path': network_path
                })
            
            # 获取所有文件
            files = []
            for entry in os.scandir(recycle_bin_path):
                if entry.is_file():
                    # 解析原始文件名和时间戳
                    filename = entry.name
                    base_name = filename.rsplit('_', 1)[0] if '_' in filename else filename
                    
                    files.append({
                        'name': filename,
                        'original_name': base_name + os.path.splitext(filename)[1],
                        'size': entry.stat().st_size,
                        'modified': entry.stat().st_mtime
                    })
            
            # 按修改时间倒序排列
            files.sort(key=lambda x: x['modified'], reverse=True)
            
            return jsonify({
                'status': 'success',
                'files': files,
                'network_path': network_path
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'获取回收站文件列表出错: {str(e)}'}), 500

    # 试验文件API - 从回收站恢复文件
    @app.route('/api/test-files/restore', methods=['POST'])
    def restore_test_file():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            filename = data.get('filename')
            if not filename:
                return jsonify({'status': 'error', 'message': '缺少文件名'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            recycle_bin_path = os.path.join(network_path, '回收站')
            recycle_file_path = os.path.join(recycle_bin_path, filename)
            
            # 检查文件是否存在
            if not os.path.exists(recycle_file_path):
                return jsonify({'status': 'error', 'message': '文件不存在'}), 404
            
            # 解析原始文件名
            base_name = filename.rsplit('_', 1)[0] if '_' in filename else filename
            original_filename = base_name + os.path.splitext(filename)[1]
            original_file_path = os.path.join(network_path, original_filename)
            
            # 如果原位置已有同名文件，添加后缀
            if os.path.exists(original_file_path):
                import time
                timestamp = int(time.time())
                base, ext = os.path.splitext(original_filename)
                original_filename = f"{base}_restored_{timestamp}{ext}"
                original_file_path = os.path.join(network_path, original_filename)
            
            # 移动文件回原位置
            import shutil
            shutil.move(recycle_file_path, original_file_path)
            
            return jsonify({
                'status': 'success',
                'message': '文件恢复成功',
                'filename': original_filename
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'恢复文件出错: {str(e)}'}), 500

    # 试验文件API - 彻底删除回收站文件
    @app.route('/api/test-files/permanent-delete', methods=['POST'])
    def permanent_delete_test_file():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            filename = data.get('filename')
            if not filename:
                return jsonify({'status': 'error', 'message': '缺少文件名'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            recycle_bin_path = os.path.join(network_path, '回收站')
            file_path = os.path.join(recycle_bin_path, filename)
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return jsonify({'status': 'error', 'message': '文件不存在'}), 404
            
            # 彻底删除文件
            os.remove(file_path)
            
            return jsonify({
                'status': 'success',
                'message': '文件已彻底删除',
                'filename': filename
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'彻底删除文件出错: {str(e)}'}), 500

    # 试验文件API - 清空回收站
    @app.route('/api/test-files/empty-recycle-bin', methods=['POST'])
    def empty_recycle_bin():
        try:
            # 网络路径
            network_path = Config.get_test_files_network_path()
            recycle_bin_path = os.path.join(network_path, '回收站')
            
            # 如果回收站不存在，直接返回成功
            if not os.path.exists(recycle_bin_path):
                return jsonify({
                    'status': 'success',
                    'message': '回收站已清空'
                })
            
            # 删除回收站中的所有文件
            deleted_count = 0
            for entry in os.scandir(recycle_bin_path):
                if entry.is_file():
                    os.remove(entry.path)
                    deleted_count += 1
            
            return jsonify({
                'status': 'success',
                'message': f'回收站已清空，共删除 {deleted_count} 个文件',
                'deleted_count': deleted_count
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'清空回收站出错: {str(e)}'}), 500

    # 试验文件API - 删除文件夹（移动到回收站）
    @app.route('/api/test-files/delete-directory', methods=['POST'])
    def delete_test_directory():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': '无有效数据'}), 400
            
            dirpath = data.get('dirpath') or data.get('dirname')
            if not dirpath:
                return jsonify({'status': 'error', 'message': '缺少文件夹路径'}), 400
            
            # 网络路径
            network_path = Config.get_test_files_network_path()
            recycle_bin_path = os.path.join(network_path, '回收站')
            dir_path = os.path.join(network_path, dirpath)
            
            # 安全检查：确保路径在基础路径内
            real_base_path = os.path.realpath(network_path)
            real_dir_path = os.path.realpath(dir_path)
            if not real_dir_path.startswith(real_base_path):
                return jsonify({'status': 'error', 'message': '非法路径访问'}), 403
            
            # 检查文件夹是否存在
            if not os.path.exists(dir_path):
                return jsonify({'status': 'error', 'message': '文件夹不存在'}), 404
            
            # 检查是否为文件夹
            if not os.path.isdir(dir_path):
                return jsonify({'status': 'error', 'message': '不是有效的文件夹'}), 400
            
            # 创建回收站目录（如果不存在）
            if not os.path.exists(recycle_bin_path):
                os.makedirs(recycle_bin_path)
            
            # 生成回收站中的文件夹名（添加时间戳避免重名）
            import time
            timestamp = int(time.time())
            dirname = os.path.basename(dirpath)
            recycle_dirname = f"{dirname}_{timestamp}"
            recycle_dir_path = os.path.join(recycle_bin_path, recycle_dirname)
            
            # 移动文件夹到回收站
            import shutil
            shutil.move(dir_path, recycle_dir_path)
            
            return jsonify({
                'status': 'success',
                'message': '文件夹已移至回收站',
                'dirname': dirname,
                'recycle_dirname': recycle_dirname
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'删除文件夹出错: {str(e)}'}), 500

    # 试验文件API - 读取文件夹内容
    @app.route('/api/test-files/list-directory', methods=['POST'])
    def list_test_directory():
        try:
            data = request.get_json()
            if not data:
                data = {}
            
            # 获取相对路径，默认为空（根目录）
            relative_path = data.get('path', '')
            
            # 网络路径
            base_path = Config.get_test_files_network_path()
            target_path = os.path.join(base_path, relative_path) if relative_path else base_path
            
            # 安全检查：确保路径在基础路径内
            real_base_path = os.path.realpath(base_path)
            real_target_path = os.path.realpath(target_path)
            if not real_target_path.startswith(real_base_path):
                return jsonify({'status': 'error', 'message': '非法路径访问'}), 403
            
            # 检查路径是否存在
            if not os.path.exists(target_path):
                return jsonify({'status': 'error', 'message': f'路径不存在: {relative_path}'}), 404
            
            # 检查是否为目录
            if not os.path.isdir(target_path):
                return jsonify({'status': 'error', 'message': '不是有效的文件夹'}), 400
            
            # 获取文件夹内容
            items = []
            for entry in os.scandir(target_path):
                # 跳过回收站文件夹
                if entry.name == '回收站':
                    continue
                    
                stat = entry.stat()
                item_info = {
                    'name': entry.name,
                    'path': os.path.join(relative_path, entry.name) if relative_path else entry.name,
                    'is_directory': entry.is_dir(),
                    'size': stat.st_size if entry.is_file() else 0,
                    'modified': stat.st_mtime
                }
                
                # 如果是文件，添加文件类型
                if entry.is_file():
                    item_info['type'] = os.path.splitext(entry.name)[1].lower()
                
                items.append(item_info)
            
            # 排序：文件夹在前，文件在后，然后按名称排序
            items.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))
            
            return jsonify({
                'status': 'success',
                'items': items,
                'current_path': relative_path,
                'full_path': target_path
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'读取文件夹出错: {str(e)}'}), 500
