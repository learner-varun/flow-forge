import json
import mimetypes
import os
import ssl
import time
import uuid
from typing import Any, Dict
from urllib import error, parse, request


class ApiClient:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.context = None if verify_ssl else ssl._create_unverified_context()

    def send(self, case: Dict[str, Any]) -> Dict[str, Any]:
        method = case.get("method", "GET").upper()
        url = self._build_url(case)
        headers = case.get("headers", {}).copy()
        body = self._encode_body(case, headers)

        req = request.Request(url=url, data=body, headers=headers, method=method)
        started = time.perf_counter()
        try:
            with request.urlopen(
                req,
                timeout=self.timeout_seconds,
                context=self.context,
            ) as resp:
                elapsed_ms = (time.perf_counter() - started) * 1000
                raw_body = resp.read()
                text_body = raw_body.decode(resp.headers.get_content_charset() or "utf-8", "replace")
                return self._response(resp.status, dict(resp.headers), text_body, elapsed_ms, None)
        except error.HTTPError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            raw_body = exc.read()
            text_body = raw_body.decode(exc.headers.get_content_charset() or "utf-8", "replace")
            return self._response(exc.code, dict(exc.headers), text_body, elapsed_ms, None)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            return self._response(None, {}, "", elapsed_ms, str(exc))

    def _build_url(self, case: Dict[str, Any]) -> str:
        endpoint = case.get("endpoint", "")
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            url = endpoint
        else:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"

        params = case.get("params") or {}
        if params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{parse.urlencode(params, doseq=True)}"
        return url

    def _encode_body(self, case: Dict[str, Any], headers: Dict[str, str]):
        if "json" in case:
            headers.setdefault("Content-Type", "application/json")
            return json.dumps(case["json"]).encode("utf-8")
        if "body" in case:
            body = case["body"]
            return body.encode("utf-8") if isinstance(body, str) else body
        if "form" in case:
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            return parse.urlencode(case["form"]).encode("utf-8")
        if "files" in case or "multipart" in case:
            boundary = f"Boundary-{uuid.uuid4().hex}"
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            
            body_parts = []
            
            # Add text fields if any
            multipart_fields = case.get("multipart", {})
            for key, val in multipart_fields.items():
                body_parts.append(f"--{boundary}".encode("utf-8"))
                body_parts.append(f'Content-Disposition: form-data; name="{key}"'.encode("utf-8"))
                body_parts.append(b"")
                body_parts.append(str(val).encode("utf-8"))
                
            # Add files
            files = case.get("files", {})
            for field_name, file_info in files.items():
                file_path = ""
                filename = ""
                content_type = "application/octet-stream"
                
                if isinstance(file_info, str):
                    file_path = file_info
                    filename = os.path.basename(file_path)
                elif isinstance(file_info, dict):
                    file_path = file_info.get("path", "")
                    filename = file_info.get("filename", os.path.basename(file_path))
                    content_type = file_info.get("content_type", "application/octet-stream")
                
                if isinstance(file_info, str) or "content_type" not in file_info:
                    guessed, _ = mimetypes.guess_type(file_path)
                    if guessed:
                        content_type = guessed
                
                file_bytes = b""
                if file_path:
                    try:
                        with open(file_path, "rb") as f:
                            file_bytes = f.read()
                    except Exception:
                        file_bytes = f"Dummy content for {filename}".encode("utf-8")
                
                body_parts.append(f"--{boundary}".encode("utf-8"))
                body_parts.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode("utf-8"))
                body_parts.append(f"Content-Type: {content_type}".encode("utf-8"))
                body_parts.append(b"")
                body_parts.append(file_bytes)
                
            body_parts.append(f"--{boundary}--".encode("utf-8"))
            body_parts.append(b"")
            return b"\r\n".join(body_parts)
        return None

    def _response(self, status_code, headers, body, elapsed_ms, error_message):
        parsed_json = None
        if body:
            try:
                parsed_json = json.loads(body)
            except json.JSONDecodeError:
                parsed_json = None

        return {
            "status_code": status_code,
            "headers": headers,
            "body": body,
            "json": parsed_json,
            "elapsed_ms": elapsed_ms,
            "error": error_message,
        }
