#!/usr/bin/env python3
"""
Convert API Test Framework Suite JSON into a Locust performance test script (Python).
"""

import sys
import os
import json
import re
import argparse

def generate_locust_script(suite_data):
    """
    Translates the suite JSON data into Python code for a LocustHttpUser.
    """
    suite_name = suite_data.get("name", "API Automation Suite")
    base_url = suite_data.get("base_url", "")
    timeout_secs = float(suite_data.get("timeout_seconds", 10.0))
    
    code = []
    
    code.append(f'"""')
    code.append(f'Locust load testing script for "{suite_name}"')
    code.append(f'Generated dynamically from suite JSON representation.')
    code.append(f'"""')
    code.append("")
    code.append("import re")
    code.append("import os")
    code.append("import mimetypes")
    code.append("import time")
    code.append("from locust import HttpUser, task, between")
    code.append("")
    
    # Add interpolation helper inside script
    code.append("def interpolate(val, session_vars):")
    code.append("    if isinstance(val, str):")
    code.append("        # Resolve {{env.VAR_NAME}}")
    code.append("        val = re.sub(r'\\{\\{env\\.([^}]+)\\}\\}', lambda m: os.environ.get(m.group(1), m.group(0)), val)")
    code.append("        # Resolve {{var_name}}")
    code.append("        for k, v in session_vars.items():")
    code.append("            placeholder = f'{{{{{k}}}}}'")
    code.append("            if placeholder in val:")
    code.append("                val = val.replace(placeholder, str(v))")
    code.append("        return val")
    code.append("    elif isinstance(val, dict):")
    code.append("        return {k: interpolate(v, session_vars) for k, v in val.items()}")
    code.append("    elif isinstance(val, list):")
    code.append("        return [interpolate(v, session_vars) for v in val]")
    code.append("    return val")
    code.append("")
    
    # Add JSON path extraction helper inside script
    code.append("def extract_json_path(data, path):")
    code.append("    if path.startswith('$') and not path.startswith('$.'):")
    code.append("        path = '$.' + path[1:]")
    code.append("    if not path.startswith('$.'):")
    code.append("        return False, None")
    code.append("    current = data")
    code.append("    tokens = re.findall(r'\\.([A-Za-z0-9_-]+)|\\[(\\d+)\\]', path[1:])")
    code.append("    for key_token, index_token in tokens:")
    code.append("        if key_token:")
    code.append("            if not isinstance(current, dict) or key_token not in current:")
    code.append("                return False, None")
    code.append("            current = current[key_token]")
    code.append("        else:")
    code.append("            index = int(index_token)")
    code.append("            if not isinstance(current, list) or index >= len(current):")
    code.append("                return False, None")
    code.append("            current = current[index]")
    code.append("    return True, current")
    code.append("")
    
    # Add assertion evaluation helper inside script
    code.append("def evaluate_locust_assertions(response, resp_json, assertions, elapsed_ms):")
    code.append("    failures = []")
    code.append("    headers = {k.lower(): v for k, v in response.headers.items()}")
    code.append("    for assertion in assertions:")
    code.append("        kind = assertion.get('type')")
    code.append("        expected = assertion.get('expected')")
    code.append("        path = assertion.get('path')")
    code.append("        try:")
    code.append("            if kind == 'status_code':")
    code.append("                actual = response.status_code")
    code.append("                if str(actual) != str(expected):")
    code.append("                    failures.append(f'Status code expected {expected}, got {actual}')")
    code.append("            elif kind == 'response_time_under_ms':")
    code.append("                if elapsed_ms > float(expected):")
    code.append("                    failures.append(f'Response time expected <= {expected}ms, got {elapsed_ms:.1f}ms')")
    code.append("            elif kind == 'header_contains':")
    code.append("                header_name = str(assertion.get('header', '')).lower()")
    code.append("                actual = headers.get(header_name)")
    code.append("                if actual is None or str(expected).lower() not in str(actual).lower():")
    code.append("                    failures.append(f'Header {header_name} expected to contain {expected}, got {actual}')")
    code.append("            elif kind == 'body_contains':")
    code.append("                if str(expected) not in response.text:")
    code.append("                    failures.append(f'Body expected to contain {expected}')")
    code.append("            elif kind == 'json_path_exists':")
    code.append("                found, actual = extract_json_path(resp_json, path)")
    code.append("                if not found:")
    code.append("                    failures.append(f'JSON Path {path} does not exist')")
    code.append("            elif kind == 'json_path_equals':")
    code.append("                found, actual = extract_json_path(resp_json, path)")
    code.append("                if not found:")
    code.append("                    failures.append(f'JSON Path {path} not found')")
    code.append("                elif str(actual) != str(expected):")
    code.append("                    failures.append(f'JSON Path {path} expected {expected}, got {actual}')")
    code.append("            elif kind == 'json_path_contains':")
    code.append("                found, actual = extract_json_path(resp_json, path)")
    code.append("                if not found or str(expected) not in str(actual):")
    code.append("                    failures.append(f'JSON Path {path} expected to contain {expected}')")
    code.append("            elif kind == 'json_path_type':")
    code.append("                found, actual = extract_json_path(resp_json, path)")
    code.append("                if not found:")
    code.append("                    failures.append(f'JSON Path {path} not found')")
    code.append("                else:")
    code.append("                    t_name = 'unknown'")
    code.append("                    if actual is None: t_name = 'null'")
    code.append("                    elif isinstance(actual, bool): t_name = 'boolean'")
    code.append("                    elif isinstance(actual, int): t_name = 'integer'")
    code.append("                    elif isinstance(actual, float): t_name = 'number'")
    code.append("                    elif isinstance(actual, str): t_name = 'string'")
    code.append("                    elif isinstance(actual, list): t_name = 'array'")
    code.append("                    elif isinstance(actual, dict): t_name = 'object'")
    code.append("                    if t_name != expected:")
    code.append("                        failures.append(f'JSON Path {path} expected type {expected}, got {t_name}')")
    code.append("            elif kind == 'json_schema':")
    code.append("                if resp_json is None:")
    code.append("                    failures.append('Response body is not valid JSON or is empty')")
    code.append("                else:")
    code.append("                    schema = expected")
    code.append("                    if isinstance(schema, str):")
    code.append("                        import json")
    code.append("                        try:")
    code.append("                            schema = json.loads(schema)")
    code.append("                        except Exception as e:")
    code.append("                            failures.append(f'Invalid JSON schema string: {str(e)}')")
    code.append("                            schema = None")
    code.append("                    if schema is not None:")
    code.append("                        try:")
    code.append("                            import jsonschema")
    code.append("                            jsonschema.validate(instance=resp_json, schema=schema)")
    code.append("                        except ImportError:")
    code.append("                            failures.append('jsonschema library is not installed for Locust schema validation')")
    code.append("                        except Exception as err:")
    code.append("                            failures.append(f'JSON schema validation failed: {str(err)}')")
    code.append("        except Exception as e:")
    code.append("            failures.append(f'Assertion error on {kind}: {str(e)}')")
    code.append("    return failures")
    code.append("")
    
    code.append("def guess_mime_type(file_path):")
    code.append("    guessed, _ = mimetypes.guess_type(file_path)")
    code.append("    return guessed or 'application/octet-stream'")
    code.append("")
    
    # Class definition
    code.append(f"class ApiUser(HttpUser):")
    code.append(f"    # Define Host target")
    code.append(f"    host = {repr(base_url)}")
    code.append(f"    # Define task wait boundaries")
    code.append(f"    wait_time = between(1, 2)")
    code.append("")
    
    # User sequential task flow
    code.append("    @task")
    code.append("    def run_api_suite(self):")
    code.append("        session_vars = {}")
    code.append("")
    
    defaults = suite_data.get("defaults", {})
    cases = suite_data.get("cases", [])
    
    for i, case in enumerate(cases):
        case_id = case.get("id", f"case_{i}")
        case_name = case.get("name", case_id)
        method = case.get("method", "GET").upper()
        endpoint = case.get("endpoint", "")
        repeat = int(case.get("repeat", defaults.get("repeat", 1)))
        
        indent = "        "
        code.append(f"{indent}# Case {i+1}: {case_name}")
        
        # Loop wrapping if repeated
        loop_indent = indent
        if repeat > 1:
            code.append(f"{indent}for _ in range({repeat}):")
            loop_indent = indent + "    "
            
        code.append(f"{loop_indent}url = interpolate({repr(endpoint)}, session_vars)")
        
        # Headers handling
        headers = case.get("headers", {}).copy()
        if "json" in case:
            if not any(k.lower() == "content-type" for k in headers.keys()):
                headers["Content-Type"] = "application/json"
        elif "form" in case:
            if not any(k.lower() == "content-type" for k in headers.keys()):
                headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif "files" in case or "multipart" in case:
            headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
            
        code.append(f"{loop_indent}headers = interpolate({repr(headers)}, session_vars)")
        
        # Query parameters
        params = case.get("params", {})
        if params:
            code.append(f"{loop_indent}params = interpolate({repr(params)}, session_vars)")
        else:
            code.append(f"{loop_indent}params = None")
            
        # Reusable arguments list
        kwargs = ["headers=headers", "params=params", f"timeout={timeout_secs}", "catch_response=True"]
        
        # Content formatting mapping
        json_payload = case.get("json")
        body_payload = case.get("body")
        form_payload = case.get("form")
        multipart_payload = case.get("multipart")
        files_payload = case.get("files")
        
        if json_payload is not None:
            code.append(f"{loop_indent}json_data = interpolate({repr(json_payload)}, session_vars)")
            kwargs.append("json=json_data")
        elif body_payload is not None:
            code.append(f"{loop_indent}body_data = interpolate({repr(body_payload)}, session_vars)")
            kwargs.append("data=body_data")
        elif form_payload is not None:
            code.append(f"{loop_indent}form_data = interpolate({repr(form_payload)}, session_vars)")
            kwargs.append("data=form_data")
        elif multipart_payload is not None:
            code.append(f"{loop_indent}multipart_data = interpolate({repr(multipart_payload)}, session_vars)")
            kwargs.append("data=multipart_data")
            
        # Files and file cleanup mappings
        if files_payload:
            code.append(f"{loop_indent}files = {{}}")
            code.append(f"{loop_indent}opened_files = []")
            code.append(f"{loop_indent}try:")
            file_indent = loop_indent + "    "
            
            for param, file_info in files_payload.items():
                if isinstance(file_info, str):
                    code.append(f"{file_indent}file_path = interpolate({repr(file_info)}, session_vars)")
                    code.append(f"{file_indent}if os.path.exists(file_path):")
                    code.append(f"{file_indent}    f = open(file_path, 'rb')")
                    code.append(f"{file_indent}    opened_files.append(f)")
                    code.append(f"{file_indent}    files[{repr(param)}] = (os.path.basename(file_path), f, guess_mime_type(file_path))")
                    code.append(f"{file_indent}else:")
                    code.append(f"{file_indent}    files[{repr(param)}] = (os.path.basename(file_path), f'Dummy content for {{os.path.basename(file_path)}}'.encode('utf-8'), guess_mime_type(file_path))")
                elif isinstance(file_info, dict):
                    code.append(f"{file_indent}file_path = interpolate({repr(file_info.get('path', ''))}, session_vars)")
                    code.append(f"{file_indent}filename = interpolate({repr(file_info.get('filename', ''))}, session_vars) or os.path.basename(file_path)")
                    code.append(f"{file_indent}content_type = interpolate({repr(file_info.get('content_type', ''))}, session_vars)")
                    code.append(f"{file_indent}if file_path and os.path.exists(file_path):")
                    code.append(f"{file_indent}    f = open(file_path, 'rb')")
                    code.append(f"{file_indent}    opened_files.append(f)")
                    code.append(f"{file_indent}    files[{repr(param)}] = (filename, f, content_type or guess_mime_type(file_path))")
                    code.append(f"{file_indent}else:")
                    code.append(f"{file_indent}    files[{repr(param)}] = (filename, f'Dummy content for {{filename}}'.encode('utf-8'), content_type or guess_mime_type(file_path))")
            
            kwargs.append("files=files")
        else:
            file_indent = loop_indent
            
        locust_method = method.lower()
        kwargs_str = ", ".join(kwargs)
        
        # Execute request and verify metrics
        code.append(f"{file_indent}start_time = time.perf_counter()")
        code.append(f"{file_indent}with self.client.{locust_method}(url, {kwargs_str}) as response:")
        resp_indent = file_indent + "    "
        code.append(f"{resp_indent}elapsed_ms = (time.perf_counter() - start_time) * 1000")
        code.append(f"{resp_indent}resp_json = None")
        code.append(f"{resp_indent}if response.text:")
        code.append(f"{resp_indent}    try:")
        code.append(f"{resp_indent}        resp_json = response.json()")
        code.append(f"{resp_indent}    except Exception:")
        code.append(f"{resp_indent}        pass")
        
        # Assertion evaluating
        assertions = case.get("assertions", [])
        code.append(f"{resp_indent}# Evaluate Assertions")
        code.append(f"{resp_indent}assertions_config = {repr(assertions)}")
        code.append(f"{resp_indent}failures = evaluate_locust_assertions(response, resp_json, assertions_config, elapsed_ms)")
        code.append(f"{resp_indent}if failures:")
        code.append(f"{resp_indent}    response.failure(', '.join(failures))")
        code.append(f"{resp_indent}else:")
        code.append(f"{resp_indent}    response.success()")
        
        # Variable extraction
        extract = case.get("extract", {})
        if extract:
            code.append(f"{resp_indent}# Extract dynamic variables")
            code.append(f"{resp_indent}if response.status_code < 400:")
            for var_name, json_path in extract.items():
                code.append(f"{resp_indent}    found, val = extract_json_path(resp_json, {repr(json_path)})")
                code.append(f"{resp_indent}    if found:")
                code.append(f"{resp_indent}        session_vars[{repr(var_name)}] = val")
                
        if files_payload:
            code.append(f"{loop_indent}finally:")
            code.append(f"{loop_indent}    for f in opened_files:")
            code.append(f"{loop_indent}        f.close()")
            
        code.append("")
        
    return "\n".join(code)

def main():
    parser = argparse.ArgumentParser(description="Convert API Automation Suite JSON to a Locust load testing script.")
    parser.add_argument("json_file", help="Path to the input suite JSON file.")
    parser.add_argument("-o", "--output", help="Path to the output Locust script. Defaults to replacing .json with _locust.py.")
    args = parser.parse_args()
    
    if not os.path.exists(args.json_file):
        print(f"Error: File '{args.json_file}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.json_file, 'r', encoding='utf-8') as f:
            suite_data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}", file=sys.stderr)
        sys.exit(1)
        
    output_path = args.output
    if not output_path:
        base, _ = os.path.splitext(args.json_file)
        output_path = base + "_locust.py"
        
    try:
        locust_content = generate_locust_script(suite_data)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(locust_content)
        print(f"Successfully converted '{args.json_file}' to '{output_path}'")
    except Exception as e:
        import traceback
        print(f"Conversion failed: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
