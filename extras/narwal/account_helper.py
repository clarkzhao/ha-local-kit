"""One-shot Narwal China SMS login and read-only device discovery, on loopback.

SMS fields/captcha behavior: official universal.narwaltech.com H5 assets,
index-CV8r49ck.js, service-CueralTG.js, useSendVerifyCode-5Ud5ihhf.js.
Login path: installed official Android app. Auth-Token header: official app
and nadavbau/narwal-integration. Device-list path: sjmotew/NarwalIntegration.
No cloud tokens or phone numbers are written to disk or returned to the UI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener

HOST = "https://cn-app.narwaltech.com"
SMS = "/user-authentication-server/v3/sms-code/generateSmsCode"
LOGIN = "/user-authentication-server/v2/login/loginByVerificationCode"
DEVICES = "/user-device-platform-server/device-info/getDeviceInfoList"
ALLOWED = {("POST", SMS), ("POST", LOGIN), ("GET", DEVICES), ("POST", DEVICES)}
DATA = Path.home() / ".config" / "ha-local-kit" / "narwal"
CSRF = secrets.token_urlsafe(32)
STATE = {"stage": "ready", "message": "请输入已有云鲸账号的手机号。"}
LOCK = threading.Lock()
TOKEN = ""
TOKEN_AT = 0.0
LAST_SMS = 0.0


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())


def api(method, path, body=None, token=""):
    if (method, path) not in ALLOWED:
        raise ValueError("接口不在只读查询工具的白名单中。")
    headers = {"Content-Type": "application/json", "Accept": "application/json", "APP-LANGUAGE": "zh_CN"}
    if token:
        headers["Auth-Token"] = token
    request = Request(HOST + path, data=None if body is None else json.dumps(body).encode(), headers=headers, method=method)
    try:
        response = OPENER.open(request, timeout=20)
    except HTTPError as exc:
        response = exc
    except (URLError, TimeoutError, OSError):
        return {"code": -1, "msg": "连接云鲸中国区接口失败，请稍后重试。"}
    with response:
        status = response.code
        try:
            result = json.loads(response.read(2_000_001).decode())
            if not isinstance(result, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            result = {"code": -1, "msg": f"接口返回 HTTP {status}，未获得 JSON 数据。"}
    result["_http_status"] = status
    return result


def success(result):
    return result.get("code") == 0 or ("code" not in result and result.get("success") is True)


def error_info(result, redactions=()):
    message = str(result.get("msg") or result.get("message") or "请求未成功。")[:500]
    for value in sorted((str(x) for x in redactions if x), key=len, reverse=True):
        message = message.replace(value, "[已隐藏]")
    return {"ok": False, "message": message, "err_code": result.get("err_code"),
            "captcha_required": result.get("err_code") == 100205201}


def identifiers(value):
    """Retain only device identifiers and labels, never arbitrary account data."""
    names = {"deviceid", "productkey", "productid", "iotid", "devicename", "robotname", "nickname", "productname", "model", "modelname", "productmodel", "firmwareversion"}
    rows = []

    def visit(item):
        if isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            record = {k: v for k, v in item.items() if re.sub(r"[^a-z0-9]", "", k.lower()) in names and isinstance(v, (str, int, float))}
            if any(re.sub(r"[^a-z0-9]", "", k.lower()) in {"deviceid", "productkey", "productid", "iotid"} for k in record):
                rows.append(record)
            for child in item.values():
                if isinstance(child, (dict, list)):
                    visit(child)
    visit(value)
    return rows


def shape(value, depth=0):
    if depth > 7:
        return type(value).__name__
    if isinstance(value, dict):
        return {k: shape(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [shape(v, depth + 1) for v in value[:2]]
    return type(value).__name__


def save_state(stage, message, **details):
    STATE.clear()
    STATE.update(stage=stage, message=message, **details)
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    (DATA / "account-helper-status.json").write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding="utf-8")


def query_devices():
    global TOKEN, TOKEN_AT
    if not TOKEN or time.monotonic() - TOKEN_AT > 1800:
        TOKEN = ""
        return {"ok": False, "message": "请先使用验证码登录。"}
    result = api("GET", DEVICES, token=TOKEN)
    # Same read-only endpoint, adapt only to an explicit method rejection.
    if result.get("_http_status") == 405:
        result = api("POST", DEVICES, {}, token=TOKEN)
    if not success(result):
        failure = error_info(result, (TOKEN,))
        save_state("query_failed", failure["message"], err_code=failure["err_code"])
        return failure
    rows = identifiers(result.get("result", result.get("data", {})))
    output = {"devices": rows, "response_shape": shape(result)}
    (DATA / "device-identifiers.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    TOKEN = ""
    TOKEN_AT = 0.0
    message = f"已读取 {len(rows)} 组设备标识，登录会话已从工具中清除。" if rows else "已登录并查询，返回格式需要继续核对；会话已清除。"
    save_state("complete" if rows else "schema_review", message, count=len(rows))
    return {"ok": True, "message": message, "devices": rows}


def action(path, body):
    global TOKEN, TOKEN_AT, LAST_SMS
    if path == "/api/query":
        return query_devices()
    if path not in {"/api/sms", "/api/login"}:
        return {"ok": False, "message": "未知操作。"}
    phone = str(body.get("mobile", "")).strip()
    if not re.fullmatch(r"1[3-9]\d{9}", phone):
        return {"ok": False, "message": "请填写 11 位中国大陆手机号。"}
    if path == "/api/sms":
        if time.monotonic() - LAST_SMS < 60:
            return {"ok": False, "message": "请等待 60 秒后再发送短信。"}
        payload = {"area_code": "86", "mobile": phone, "code_type": 1}
        captcha = str(body.get("captcha_verify_param", ""))
        if captcha:
            payload["captcha_verify_param"] = captcha
        result = api("POST", SMS, payload)
        if not success(result):
            failure = error_info(result, (phone, captcha))
            save_state("captcha_required" if failure["captcha_required"] else "sms_failed", failure["message"], err_code=failure["err_code"])
            return failure
        LAST_SMS = time.monotonic()
        save_state("sms_sent", "验证码已发送，请在本页输入。")
        return {"ok": True, "message": STATE["message"]}
    code = str(body.get("verification", "")).strip()
    if not re.fullmatch(r"\d{6}", code):
        return {"ok": False, "message": "请填写 6 位短信验证码。"}
    result = api("POST", LOGIN, {"area_code": 86, "mobile": phone, "verification": code, "code_type": 1, "default_nickname": "一个云鲸用户"})
    if not success(result):
        failure = error_info(result, (phone, code))
        save_state("login_failed", failure["message"], err_code=failure["err_code"])
        return failure
    data = result.get("result", result.get("data", {}))
    TOKEN = data.get("token", "") if isinstance(data, dict) else ""
    if not isinstance(TOKEN, str) or not TOKEN:
        TOKEN = ""
        save_state("login_schema_review", "登录响应格式需要继续核对。", response_shape=shape(result))
        return {"ok": False, "message": STATE["message"]}
    TOKEN_AT = time.monotonic()
    save_state("querying", "登录成功，正在读取设备标识。")
    return query_devices()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, body, status=200, content_type="application/json; charset=utf-8"):
        encoded = body.encode("utf-8") if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(encoded)

    def local_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.local_host():
            return self.send({"ok": False}, 403)
        if self.path == "/":
            html = Path(__file__).with_name("narwal_account_helper.html").read_text(encoding="utf-8").replace("__CSRF__", CSRF)
            return self.send(html, content_type="text/html; charset=utf-8")
        if self.path == "/api/status":
            return self.send(dict(STATE))
        self.send({"ok": False}, 404)

    def do_POST(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if not self.local_host() or self.headers.get("Origin") != origin or self.headers.get("X-CSRF-Token") != CSRF:
            return self.send({"ok": False, "message": "请求来源无效。"}, 403)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16_384 or not self.headers.get("Content-Type", "").startswith("application/json"):
                raise ValueError()
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            return self.send({"ok": False, "message": "请求格式错误。"}, 400)
        if not LOCK.acquire(blocking=False):
            return self.send({"ok": False, "message": "已有请求正在处理。"}, 409)
        try:
            self.send(action(self.path, body))
        except Exception:
            # Do not expose exception values: upstream failures may contain secrets.
            save_state("error", "查询工具遇到错误，请告知助手核对。")
            self.send({"ok": False, "message": STATE["message"]}, 500)
        finally:
            LOCK.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--state-dir", type=Path, default=DATA)
    args = parser.parse_args()
    DATA = args.state_dir
    os.umask(0o077)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    save_state("ready", STATE["message"])
    print(f"Narwal local helper: http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()
