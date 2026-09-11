"""羿射旭 Windows 本地文件打开器。"""
import argparse
import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import requests

HOST = "127.0.0.1"
PORT = 17890
WORKSPACE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "YishexuWorkspace"
APP_DIR = WORKSPACE_DIR
SESSIONS_PATH = APP_DIR / "sessions.json"
SESSION_LOCK = threading.RLock()
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173", "http://localhost:3000", "http://127.0.0.1:3000"}
LOCAL_HOST_NAMES = {"localhost", "127.0.0.1", os.environ.get("COMPUTERNAME", "").lower()}


def is_private_host(host):
    """判断是否本机或局域网地址，用于放行内网访问来源。"""
    if not host:
        return False
    host = host.lower()
    if host in LOCAL_HOST_NAMES:
        return True
    parts = host.split(".")
    if len(parts) != 4:
        return False
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return False
    if any(number < 0 or number > 255 for number in numbers):
        return False
    if numbers[0] == 10 or numbers[0] == 127:
        return True
    if numbers[0] == 192 and numbers[1] == 168:
        return True
    if numbers[0] == 172 and 16 <= numbers[1] <= 31:
        return True
    return False


class OpenerError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def load_sessions():
    with SESSION_LOCK:
        if not SESSIONS_PATH.exists():
            return {}
        try:
            data = json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}


def save_sessions(sessions):
    with SESSION_LOCK:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = SESSIONS_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, SESSIONS_PATH)


def safe_file_name(file_name):
    name = Path(str(file_name)).name
    if not name or name in (".", ".."):
        raise OpenerError("文件名无效")
    return name


def validate_server_url(server_url):
    parsed = urlparse(str(server_url))
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise OpenerError("服务器地址无效")
    return str(server_url).rstrip("/")


def request_server(method, server_url, path, access_token, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = "Bearer " + str(access_token)
    try:
        response = requests.request(method, validate_server_url(server_url) + path, headers=headers, timeout=60, **kwargs)
    except requests.RequestException as exc:
        raise OpenerError("无法连接文件服务器：" + str(exc), 502) from exc
    if not response.ok:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        raise OpenerError(payload.get("message") or "文件服务器请求失败", response.status_code)
    return response


def versioned_name(file_name, version):
    """在扩展名前加上版本号，便于用户直观区分本地打开的是哪个版本。"""
    name = safe_file_name(file_name)
    if not version:
        return name
    stem, dot, suffix = name.rpartition(".")
    if dot:
        return f"{stem}_v{version}.{suffix}"
    return f"{name}_v{version}"


def session_path(project_id, relative_path, file_name, version=None):
    """本地文件保持与网页相同的目录结构，并在文件名中标注版本号。"""
    normalized = str(relative_path or "").replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part not in ("", ".", "..")]
    if not parts:
        parts = [str(file_name)]
    target = WORKSPACE_DIR / str(project_id)
    for part in parts[:-1]:
        target = target / safe_file_name(part)
    return target / versioned_name(parts[-1], version)


def open_file(payload):
    required = ("server_url", "token", "file_id", "checkout_token", "project_id", "file_name")
    if any(not payload.get(key) for key in required):
        raise OpenerError("打开文件参数不完整")
    file_id = str(payload["file_id"])
    checkout_version = int(payload.get("checkout_version", payload.get("base_version", 0)) or 0)
    target_path = session_path(payload["project_id"], payload.get("relative_path"), payload["file_name"], checkout_version)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    response = request_server("GET", payload["server_url"], f"/api/workspace/files/{file_id}/checkout/download?checkout_token={payload['checkout_token']}", payload["token"], stream=True)
    temp_path = target_path.with_suffix(target_path.suffix + ".download")
    try:
        with temp_path.open("wb") as stream:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    stream.write(chunk)
        os.replace(temp_path, target_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    session = {"server_url": validate_server_url(payload["server_url"]), "token": str(payload["token"]), "file_id": file_id, "project_id": str(payload["project_id"]), "file_name": safe_file_name(payload["file_name"]), "checkout_token": str(payload["checkout_token"]), "checkout_version": int(payload.get("checkout_version", payload.get("base_version", 0))), "path": str(target_path)}
    sessions = load_sessions()
    sessions[file_id] = session
    save_sessions(sessions)
    try:
        os.startfile(target_path)
    except OSError as exc:
        raise OpenerError("无法使用本地默认软件打开文件：" + str(exc), 500) from exc
    return session


def remove_session(file_id, session):
    path = Path(session.get("path", ""))
    try:
        if path.exists():
            path.unlink()
        # 逐级清理检入后产生的空目录，恢复到工作根目录为止。
        parent = path.parent
        while parent != WORKSPACE_DIR and WORKSPACE_DIR in parent.parents:
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
            else:
                break
    except OSError:
        pass
    sessions = load_sessions()
    sessions.pop(file_id, None)
    save_sessions(sessions)


def checkin_file(payload):
    file_id = str(payload.get("file_id", ""))
    session = load_sessions().get(file_id)
    if not session:
        raise OpenerError("未找到该文件的本地检出会话", 404)
    path = Path(session["path"])
    try:
        stream = path.open("rb")
    except (PermissionError, OSError) as exc:
        raise OpenerError("无法读取本地文件，请先保存并关闭文件后重试", 409) from exc
    try:
        response = request_server("POST", session["server_url"], f"/api/workspace/files/{file_id}/checkin", session["token"], files={"file": (session["file_name"], stream)}, data={"checkout_token": session["checkout_token"], "checkout_version": str(session["checkout_version"])})
    finally:
        stream.close()
    result = response.json()
    remove_session(file_id, session)
    return result


def cancel_file(payload):
    file_id = str(payload.get("file_id", ""))
    session = load_sessions().get(file_id)
    if not session:
        raise OpenerError("未找到该文件的本地检出会话", 404)
    response = request_server("POST", session["server_url"], f"/api/workspace/files/{file_id}/cancel-checkout", session["token"], json={"token": session["checkout_token"]})
    result = response.json()
    remove_session(file_id, session)
    return result


class FileOpenerHandler(BaseHTTPRequestHandler):
    server_version = "YishexuFileOpener/2.0"

    def _origin_allowed(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        if origin in ALLOWED_ORIGINS:
            return True
        # 允许通过本机名或局域网地址访问前端时的跨域请求。
        return is_private_host(urlparse(origin).hostname)

    def _cors_headers(self):
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS or is_private_host(urlparse(origin or "").hostname):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise OpenerError("请求 JSON 无效") from exc

    def do_OPTIONS(self):
        if not self._origin_allowed():
            self._send_json(403, {"status": "error", "message": "不允许的请求来源"})
            return
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"status": "error", "message": "接口不存在"})

    def do_POST(self):
        if not self._origin_allowed():
            self._send_json(403, {"status": "error", "message": "不允许的请求来源"})
            return
        try:
            action = {"/open": open_file, "/checkin": checkin_file, "/cancel": cancel_file}.get(self.path)
            if not action:
                raise OpenerError("接口不存在", 404)
            result = action(self._read_json())
            self._send_json(200, {"status": "success", "result": result})
        except OpenerError as exc:
            self._send_json(exc.status_code, {"status": "error", "message": str(exc)})
        except Exception as exc:
            self._send_json(500, {"status": "error", "message": "本地打开器处理失败：" + str(exc)})

    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args))


def run_service():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), FileOpenerHandler)
    print(f"羿射旭本地文件打开器已启动：http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


def command_line(args):
    if args.command == "open":
        return open_file({"server_url": args.server_url, "token": args.token, "file_id": args.file_id, "checkout_token": args.checkout_token, "project_id": args.project_id, "file_name": args.file_name or Path(args.target_path).name, "relative_path": args.relative_path, "checkout_version": args.checkout_version})
    session = load_sessions().get(args.file_id)
    if not session:
        raise OpenerError("未找到该文件的本地检出会话", 404)
    session["path"] = args.target_path
    sessions = load_sessions()
    sessions[args.file_id] = session
    save_sessions(sessions)
    return checkin_file({"file_id": args.file_id})


def main():
    parser = argparse.ArgumentParser(description="羿射旭本地文件打开器")
    sub = parser.add_subparsers(dest="command")
    open_parser = sub.add_parser("open")
    open_parser.add_argument("server_url")
    open_parser.add_argument("token")
    open_parser.add_argument("file_id")
    open_parser.add_argument("checkout_token")
    open_parser.add_argument("target_path")
    open_parser.add_argument("--project-id", default="default")
    open_parser.add_argument("--file-name", default="")
    open_parser.add_argument("--relative-path", default="")
    open_parser.add_argument("--checkout-version", type=int, default=0)
    checkin_parser = sub.add_parser("checkin")
    checkin_parser.add_argument("server_url")
    checkin_parser.add_argument("token")
    checkin_parser.add_argument("file_id")
    checkin_parser.add_argument("checkout_token")
    checkin_parser.add_argument("target_path")
    parser.add_argument("--service", action="store_true")
    args = parser.parse_args()
    if args.service:
        run_service()
    elif args.command:
        if args.command == "open" and not args.file_name:
            args.file_name = Path(args.target_path).name
        result = command_line(args)
        print(json.dumps(result, ensure_ascii=False))
    else:
        run_service()


if __name__ == "__main__":
    main()
