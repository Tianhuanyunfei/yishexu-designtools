import hashlib
import json
import os
import shutil
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config.config import Config


class WorkspaceStore:
    _lock = threading.RLock()

    def __init__(self):
        self.root = Path(Config.WORKSPACE_DATA_DIR)
        self.storage = self.root / 'storage'
        self.manifest_path = self.root / 'manifest.json'
        self.root.mkdir(parents=True, exist_ok=True)
        self.storage.mkdir(parents=True, exist_ok=True)
        self._ensure_manifest()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _is_lock_expired(lock):
        expires_at = lock.get('expires_at')
        if not expires_at:
            return False
        try:
            expires = datetime.fromisoformat(expires_at)
        except ValueError:
            return False
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= datetime.now(timezone.utc)

    def _ensure_manifest(self):
        if not self.manifest_path.exists():
            self._write({'projects': {}, 'files': {}, 'versions': {}, 'locks': {}})

    def _read(self):
        with self.manifest_path.open('r', encoding='utf-8') as stream:
            return json.load(stream)

    def _write(self, data):
        temp_path = self.manifest_path.with_suffix('.tmp')
        with temp_path.open('w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temp_path, self.manifest_path)

    def _mutate(self, callback):
        with self._lock:
            data = self._read()
            result = callback(data)
            self._write(data)
            return result

    def list_projects(self, user_id):
        with self._lock:
            data = self._read()
            return [project for project in data['projects'].values() if user_id in project['members']]

    def create_project(self, name, user_id, description=''):
        project_id = str(uuid.uuid4())
        project = {
            'id': project_id,
            'name': name,
            'description': description,
            'owner_id': user_id,
            'members': {user_id: 'owner'},
            'created_at': self._now(),
            'updated_at': self._now(),
        }

        def callback(data):
            data['projects'][project_id] = project
            return project

        self._mutate(callback)
        (self.storage / project_id / 'versions').mkdir(parents=True, exist_ok=True)
        return project

    def get_project(self, project_id, user_id):
        with self._lock:
            project = self._read()['projects'].get(project_id)
            if not project or user_id not in project['members']:
                return None
            return project

    def add_member(self, project_id, actor_id, user_id, role='editor'):
        def callback(data):
            project = data['projects'].get(project_id)
            if not project or project['members'].get(actor_id) not in ('owner', 'admin'):
                return None
            project['members'][user_id] = role
            project['updated_at'] = self._now()
            return project

        return self._mutate(callback)

    def list_files(self, project_id, user_id, parent_path=''):
        if not self.get_project(project_id, user_id):
            return None
        normalized_parent = parent_path.replace('\\', '/').strip('/')
        with self._lock:
            data = self._read()
            items = []
            directories = set()
            for file_entry in data['files'].values():
                if file_entry['project_id'] != project_id or file_entry.get('deleted_at'):
                    continue
                relative_path = file_entry['relative_path']
                directory = os.path.dirname(relative_path).replace('\\', '/')
                if directory == normalized_parent:
                    item = dict(file_entry)
                    item['is_directory'] = False
                    item['lock'] = data['locks'].get(file_entry['id'])
                    items.append(item)
                    continue
                prefix = f'{normalized_parent}/' if normalized_parent else ''
                if relative_path.startswith(prefix):
                    remaining = relative_path[len(prefix):]
                    if '/' in remaining:
                        directories.add(remaining.split('/', 1)[0])

            for name in directories:
                items.append({
                    'id': f'directory:{normalized_parent}/{name}',
                    'name': name,
                    'relative_path': f'{normalized_parent}/{name}'.strip('/'),
                    'is_directory': True,
                })
            return sorted(items, key=lambda item: (not item['is_directory'], item['name'].lower()))

    def save_file(self, project_id, user_id, relative_path, content, base_version=None, lock_token=None):
        project = self.get_project(project_id, user_id)
        if not project or project['members'].get(user_id) not in ('owner', 'admin', 'editor'):
            return {'status': 'forbidden'}

        normalized_path = relative_path.replace('\\', '/').strip('/')
        path_parts = normalized_path.split('/')
        if not normalized_path or any(part in ('', '.', '..') for part in path_parts):
            return {'status': 'invalid_path'}

        with self._lock:
            data = self._read()
            file_entry = next(
                (item for item in data['files'].values()
                 if item['project_id'] == project_id and item['relative_path'] == normalized_path and not item.get('deleted_at')),
                None,
            )
            if file_entry and base_version is not None and file_entry['current_version'] != int(base_version):
                return {'status': 'conflict', 'file': file_entry}

            if file_entry:
                lock = data['locks'].get(file_entry['id'])
                if lock and lock['user_id'] != user_id and lock.get('token') != lock_token:
                    return {'status': 'locked', 'lock': lock}

            file_id = file_entry['id'] if file_entry else str(uuid.uuid4())
            version_number = file_entry['current_version'] + 1 if file_entry else 1
            version_id = str(uuid.uuid4())
            version_path = self.storage / project_id / 'versions' / file_id
            version_path.mkdir(parents=True, exist_ok=True)
            content_path = version_path / f'v{version_number:06d}'
            content_path.write_bytes(content)
            now = self._now()
            content_hash = hashlib.sha256(content).hexdigest()

            if not file_entry:
                file_entry = {
                    'id': file_id,
                    'project_id': project_id,
                    'relative_path': normalized_path,
                    'name': os.path.basename(normalized_path),
                    'current_version': 0,
                    'created_by': user_id,
                    'created_at': now,
                }
                data['files'][file_id] = file_entry

            file_entry.update({
                'current_version': version_number,
                'size': len(content),
                'content_hash': content_hash,
                'updated_by': user_id,
                'updated_at': now,
                'deleted_at': None,
            })
            data['versions'][version_id] = {
                'id': version_id,
                'file_id': file_id,
                'version': version_number,
                'path': str(content_path),
                'size': len(content),
                'content_hash': content_hash,
                'created_by': user_id,
                'created_at': now,
            }
            self._write(data)
            return {'status': 'success', 'file': file_entry, 'version': data['versions'][version_id]}

    def get_file(self, file_id, user_id):
        with self._lock:
            data = self._read()
            file_entry = data['files'].get(file_id)
            if not file_entry or file_entry.get('deleted_at') or not self.get_project(file_entry['project_id'], user_id):
                return None
            return file_entry

    def get_current_content(self, file_entry):
        with self._lock:
            data = self._read()
            version = next(
                item for item in data['versions'].values()
                if item['file_id'] == file_entry['id'] and item['version'] == file_entry['current_version']
            )
            return Path(version['path']).read_bytes()

    def list_versions(self, file_id, user_id):
        file_entry = self.get_file(file_id, user_id)
        if not file_entry:
            return None
        with self._lock:
            return sorted(
                [item for item in self._read()['versions'].values() if item['file_id'] == file_id],
                key=lambda item: item['version'], reverse=True,
            )

    def get_version(self, file_id, user_id, version_id):
        if not self.get_file(file_id, user_id):
            return None
        with self._lock:
            for item in self._read()['versions'].values():
                if item['file_id'] == file_id and item['id'] == version_id:
                    return item
        return None

    def get_version_content(self, file_id, user_id, version_id):
        version = self.get_version(file_id, user_id, version_id)
        if not version:
            return None
        try:
            return Path(version['path']).read_bytes()
        except OSError:
            return None

    def checkout_file(self, file_id, user_id, version_id=None):
        file_entry = self.get_file(file_id, user_id)
        if not file_entry:
            return None, 'not_found'
        project = self.get_project(file_entry['project_id'], user_id)
        if not project or project['members'].get(user_id) not in ('owner', 'admin', 'editor'):
            return None, 'forbidden'
        with self._lock:
            data = self._read()
            file_entry = data['files'].get(file_id)
            source_version = None
            if version_id:
                source_version = next(
                    (item for item in data['versions'].values()
                     if item['id'] == version_id and item['file_id'] == file_id),
                    None,
                )
                if not source_version:
                    return None, 'not_found'
            lock = data['locks'].get(file_id)
            if lock:
                if lock['user_id'] == user_id:
                    return {'file': file_entry, 'lock': lock}, 'success'
                return lock, 'locked'
            now = datetime.now(timezone.utc)
            source_number = source_version['version'] if source_version else file_entry['current_version']
            new_lock = {
                'file_id': file_id,
                'user_id': user_id,
                'token': str(uuid.uuid4()),
                'checkout_version': source_number,
                'base_version': source_number,
                # 基于历史版本检出时，检入不要求服务器仍停留在该版本，可直接在最新版之上升版。
                'based_on_history': bool(source_version) and source_number != file_entry['current_version'],
                'source_version_id': source_version['id'] if source_version else '',
                'source_version': source_number,
                'created_at': now.isoformat(),
                'expires_at': (now + timedelta(hours=4)).isoformat(),
                'original_path': file_entry['relative_path'],
                'original_name': file_entry['name'],
            }
            data['locks'][file_id] = new_lock
            self._write(data)
            return {'file': file_entry, 'lock': new_lock}, 'success'

    def checkout(self, file_id, user_id, version_id=None):
        return self.checkout_file(file_id, user_id, version_id)

    def checkin(self, file_id, user_id, token, checkout_version, content):
        with self._lock:
            data = self._read()
            file_entry = data['files'].get(file_id)
            if not file_entry or file_entry.get('deleted_at'):
                return {'status': 'not_found'}
            project = data['projects'].get(file_entry['project_id'])
            if not project or user_id not in project['members']:
                return {'status': 'forbidden'}
            lock = data['locks'].get(file_id)
            if not lock:
                return {'status': 'invalid_lock'}
            if lock.get('user_id') != user_id or lock.get('token') != token:
                return {'status': 'forbidden', 'lock': lock}
            try:
                expected_version = int(checkout_version)
            except (TypeError, ValueError):
                return {'status': 'conflict', 'file': file_entry}
            if lock.get('checkout_version', lock.get('base_version')) != expected_version:
                return {'status': 'conflict', 'file': file_entry}
            # 基于历史版本检出时，允许服务器版本已经前进，直接在最新版之上升版。
            if not lock.get('based_on_history') and file_entry['current_version'] != expected_version:
                return {'status': 'conflict', 'file': file_entry}
            version_number = file_entry['current_version'] + 1
            version_path = self.storage / file_entry['project_id'] / 'versions' / file_id
            version_path.mkdir(parents=True, exist_ok=True)
            content_path = version_path / f'v{version_number:06d}'
            try:
                content_path.write_bytes(content)
            except OSError as exc:
                return {'status': 'storage_error', 'message': str(exc)}
            now = self._now()
            version_id = str(uuid.uuid4())
            version = {
                'id': version_id, 'file_id': file_id, 'version': version_number,
                'path': str(content_path), 'size': len(content),
                'content_hash': hashlib.sha256(content).hexdigest(),
                'created_by': user_id, 'created_at': now,
                'base_version': lock.get('source_version', expected_version),
                'base_version_id': lock.get('source_version_id', ''),
                'from_history': bool(lock.get('based_on_history')),
            }
            file_entry.update({
                'current_version': version_number, 'size': len(content),
                'content_hash': version['content_hash'], 'updated_by': user_id,
                'updated_at': now, 'deleted_at': None,
            })
            data['versions'][version_id] = version
            del data['locks'][file_id]
            self._write(data)
            return {'status': 'success', 'file': file_entry, 'version': version}

    def touch_checkout(self, file_id, user_id, token):
        def callback(data):
            lock = data['locks'].get(file_id)
            if not lock:
                return 'invalid_lock'
            if lock.get('user_id') != user_id or lock.get('token') != token:
                return 'forbidden'
            lock['expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
            return lock
        return self._mutate(callback)

    def cancel_checkout(self, file_id, user_id, token):
        def callback(data):
            file_entry = data['files'].get(file_id)
            if not file_entry or file_entry.get('deleted_at'):
                return 'not_found'
            project = data['projects'].get(file_entry['project_id'])
            if not project or user_id not in project['members']:
                return 'forbidden'
            lock = data['locks'].get(file_id)
            if not lock:
                return 'invalid_lock'
            if self._is_lock_expired(lock):
                del data['locks'][file_id]
                return 'invalid_lock'
            if lock['user_id'] != user_id or lock.get('token') != token:
                return 'forbidden'
            del data['locks'][file_id]
            return 'success'
        return self._mutate(callback)

    def acquire_lock(self, file_id, user_id):
        file_entry = self.get_file(file_id, user_id)
        if not file_entry:
            return None, 'not_found'
        token = str(uuid.uuid4())

        def callback(data):
            lock = data['locks'].get(file_id)
            if lock and lock['user_id'] != user_id:
                return lock, 'locked'
            new_lock = {'file_id': file_id, 'user_id': user_id, 'token': token, 'created_at': self._now()}
            data['locks'][file_id] = new_lock
            return new_lock, 'success'

        return self._mutate(callback)

    def release_lock(self, file_id, user_id, token):
        def callback(data):
            lock = data['locks'].get(file_id)
            if not lock or lock['user_id'] != user_id or lock['token'] != token:
                return False
            del data['locks'][file_id]
            return True

        return self._mutate(callback)

    def get_lock(self, file_id):
        with self._lock:
            return self._read()['locks'].get(file_id)

    def _can_delete(self, data, project_id, user_id):
        project = data['projects'].get(project_id)
        if not project or user_id not in project['members']:
            return False
        return project['members'].get(user_id) in ('owner', 'admin', 'editor')

    def delete_file(self, file_id, user_id):
        with self._lock:
            data = self._read()
            file_entry = data['files'].get(file_id)
            if not file_entry or file_entry.get('deleted_at'):
                return 'not_found'
            if not self._can_delete(data, file_entry['project_id'], user_id):
                return 'forbidden'
            lock = data['locks'].get(file_id)
            if lock and lock['user_id'] != user_id:
                return 'locked'
            data['locks'].pop(file_id, None)
            file_entry['deleted_at'] = self._now()
            file_entry['deleted_by'] = user_id
            self._write(data)
            return 'success'

    def delete_directory(self, project_id, user_id, relative_path):
        normalized_path = relative_path.replace('\\', '/').strip('/')
        if not normalized_path:
            return 'invalid_path'
        with self._lock:
            data = self._read()
            if not self._can_delete(data, project_id, user_id):
                return 'forbidden'
            prefix = f'{normalized_path}/'
            targets = [
                item for item in data['files'].values()
                if item['project_id'] == project_id
                and not item.get('deleted_at')
                and item['relative_path'].startswith(prefix)
            ]
            if not targets:
                return 'not_found'
            for item in targets:
                lock = data['locks'].get(item['id'])
                if lock and lock['user_id'] != user_id:
                    return 'locked'
            now = self._now()
            for item in targets:
                data['locks'].pop(item['id'], None)
                item['deleted_at'] = now
                item['deleted_by'] = user_id
            self._write(data)
            return 'success'

    def delete_project(self, project_id, user_id):
        with self._lock:
            data = self._read()
            project = data['projects'].get(project_id)
            if not project:
                return 'not_found'
            if project['members'].get(user_id) != 'owner':
                return 'forbidden'
            file_ids = [item['id'] for item in data['files'].values() if item['project_id'] == project_id]
            for file_id in file_ids:
                data['files'].pop(file_id, None)
                data['locks'].pop(file_id, None)
            for version_id in [
                item['id'] for item in data['versions'].values() if item['file_id'] in file_ids
            ]:
                data['versions'].pop(version_id, None)
            data['projects'].pop(project_id, None)
            self._write(data)
            shutil.rmtree(self.storage / project_id, ignore_errors=True)
            return 'success'
