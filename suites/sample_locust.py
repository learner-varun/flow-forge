"""
Locust load testing script for "ZiffySign Documents Flow Suite"
Generated dynamically from suite JSON representation.
"""

import re
import os
import mimetypes
import time
from locust import HttpUser, task, between

def interpolate(val, session_vars):
    if isinstance(val, str):
        # Resolve {{env.VAR_NAME}}
        val = re.sub(r'\{\{env\.([^}]+)\}\}', lambda m: os.environ.get(m.group(1), m.group(0)), val)
        # Resolve {{var_name}}
        for k, v in session_vars.items():
            placeholder = f'{{{{{k}}}}}'
            if placeholder in val:
                val = val.replace(placeholder, str(v))
        return val
    elif isinstance(val, dict):
        return {k: interpolate(v, session_vars) for k, v in val.items()}
    elif isinstance(val, list):
        return [interpolate(v, session_vars) for v in val]
    return val

def extract_json_path(data, path):
    if path.startswith('$') and not path.startswith('$.'):
        path = '$.' + path[1:]
    if not path.startswith('$.'):
        return False, None
    current = data
    tokens = re.findall(r'\.([A-Za-z0-9_-]+)|\[(\d+)\]', path[1:])
    for key_token, index_token in tokens:
        if key_token:
            if not isinstance(current, dict) or key_token not in current:
                return False, None
            current = current[key_token]
        else:
            index = int(index_token)
            if not isinstance(current, list) or index >= len(current):
                return False, None
            current = current[index]
    return True, current

def evaluate_locust_assertions(response, resp_json, assertions, elapsed_ms):
    failures = []
    headers = {k.lower(): v for k, v in response.headers.items()}
    for assertion in assertions:
        kind = assertion.get('type')
        expected = assertion.get('expected')
        path = assertion.get('path')
        try:
            if kind == 'status_code':
                actual = response.status_code
                if str(actual) != str(expected):
                    failures.append(f'Status code expected {expected}, got {actual}')
            elif kind == 'response_time_under_ms':
                if elapsed_ms > float(expected):
                    failures.append(f'Response time expected <= {expected}ms, got {elapsed_ms:.1f}ms')
            elif kind == 'header_contains':
                header_name = str(assertion.get('header', '')).lower()
                actual = headers.get(header_name)
                if actual is None or str(expected).lower() not in str(actual).lower():
                    failures.append(f'Header {header_name} expected to contain {expected}, got {actual}')
            elif kind == 'body_contains':
                if str(expected) not in response.text:
                    failures.append(f'Body expected to contain {expected}')
            elif kind == 'json_path_exists':
                found, actual = extract_json_path(resp_json, path)
                if not found:
                    failures.append(f'JSON Path {path} does not exist')
            elif kind == 'json_path_equals':
                found, actual = extract_json_path(resp_json, path)
                if not found:
                    failures.append(f'JSON Path {path} not found')
                elif str(actual) != str(expected):
                    failures.append(f'JSON Path {path} expected {expected}, got {actual}')
            elif kind == 'json_path_contains':
                found, actual = extract_json_path(resp_json, path)
                if not found or str(expected) not in str(actual):
                    failures.append(f'JSON Path {path} expected to contain {expected}')
            elif kind == 'json_path_type':
                found, actual = extract_json_path(resp_json, path)
                if not found:
                    failures.append(f'JSON Path {path} not found')
                else:
                    t_name = 'unknown'
                    if actual is None: t_name = 'null'
                    elif isinstance(actual, bool): t_name = 'boolean'
                    elif isinstance(actual, int): t_name = 'integer'
                    elif isinstance(actual, float): t_name = 'number'
                    elif isinstance(actual, str): t_name = 'string'
                    elif isinstance(actual, list): t_name = 'array'
                    elif isinstance(actual, dict): t_name = 'object'
                    if t_name != expected:
                        failures.append(f'JSON Path {path} expected type {expected}, got {t_name}')
        except Exception as e:
            failures.append(f'Assertion error on {kind}: {str(e)}')
    return failures

def guess_mime_type(file_path):
    guessed, _ = mimetypes.guess_type(file_path)
    return guessed or 'application/octet-stream'

class ApiUser(HttpUser):
    # Define Host target
    host = 'https://dev-apis.ziffysign.com'
    # Define task wait boundaries
    wait_time = between(1, 2)

    @task
    def run_api_suite(self):
        session_vars = {}

        # Case 1: Authenticate user to obtain access token
        url = interpolate('/api/v1/auth/login', session_vars)
        headers = interpolate({'accept': 'application/json', 'Content-Type': 'application/json'}, session_vars)
        params = None
        json_data = interpolate({'email': 'training@prologicians.com', 'password': 'Testing@123'}, session_vars)
        start_time = time.perf_counter()
        with self.client.post(url, headers=headers, params=params, timeout=10.0, catch_response=True, json=json_data) as response:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            resp_json = None
            if response.text:
                try:
                    resp_json = response.json()
                except Exception:
                    pass
            # Evaluate Assertions
            assertions_config = [{'type': 'status_code', 'expected': '200'}, {'type': 'json_path_exists', 'path': '$.data.accessToken'}]
            failures = evaluate_locust_assertions(response, resp_json, assertions_config, elapsed_ms)
            if failures:
                response.failure(', '.join(failures))
            else:
                response.success()
            # Extract dynamic variables
            if response.status_code < 400:
                found, val = extract_json_path(resp_json, '$.data.accessToken')
                if found:
                    session_vars['auth_token'] = val

        # Case 2: Initial document upload (creates envelope)
        url = interpolate('/api/v1/documents/upload', session_vars)
        headers = interpolate({'accept': 'application/json, text/plain, */*', 'authorization': 'Bearer {{auth_token}}'}, session_vars)
        params = None
        files = {}
        opened_files = []
        try:
            file_path = interpolate('suites/test_document.pdf', session_vars)
            if os.path.exists(file_path):
                f = open(file_path, 'rb')
                opened_files.append(f)
                files['file'] = (os.path.basename(file_path), f, guess_mime_type(file_path))
            else:
                files['file'] = (os.path.basename(file_path), f'Dummy content for {os.path.basename(file_path)}'.encode('utf-8'), guess_mime_type(file_path))
            start_time = time.perf_counter()
            with self.client.post(url, headers=headers, params=params, timeout=10.0, catch_response=True, files=files) as response:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                resp_json = None
                if response.text:
                    try:
                        resp_json = response.json()
                    except Exception:
                        pass
                # Evaluate Assertions
                assertions_config = [{'type': 'status_code', 'expected': '201'}, {'type': 'json_path_exists', 'path': '$.data.envelopeId'}]
                failures = evaluate_locust_assertions(response, resp_json, assertions_config, elapsed_ms)
                if failures:
                    response.failure(', '.join(failures))
                else:
                    response.success()
                # Extract dynamic variables
                if response.status_code < 400:
                    found, val = extract_json_path(resp_json, '$.data.envelopeId')
                    if found:
                        session_vars['envelope_id'] = val
        finally:
            for f in opened_files:
                f.close()

        # Case 3: Imported GET case for /api/v1/health
        url = interpolate('/api/v1/health', session_vars)
        headers = interpolate({}, session_vars)
        params = None
        start_time = time.perf_counter()
        with self.client.get(url, headers=headers, params=params, timeout=10.0, catch_response=True) as response:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            resp_json = None
            if response.text:
                try:
                    resp_json = response.json()
                except Exception:
                    pass
            # Evaluate Assertions
            assertions_config = [{'type': 'status_code', 'expected': '200'}]
            failures = evaluate_locust_assertions(response, resp_json, assertions_config, elapsed_ms)
            if failures:
                response.failure(', '.join(failures))
            else:
                response.success()
