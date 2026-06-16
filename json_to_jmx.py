#!/usr/bin/env python3
"""
Convert API Test Framework Suite JSON into JMeter JMX (XML) format.
"""

import sys
import os
import json
import re
import urllib.parse
import mimetypes
import xml.etree.ElementTree as ET

def translate_placeholders(val):
    """
    Translates variable placeholders from the test framework format to JMeter format:
    - {{env.VAR_NAME}} -> ${__groovy(System.getenv('VAR_NAME'))}
    - {{var_name}} -> ${var_name}
    """
    if isinstance(val, str):
        # Resolve {{env.VAR_NAME}} to JMeter Groovy environment call
        val = re.sub(r"\{\{env\.([^}]+)\}\}", r"${__groovy(System.getenv('\1'))}", val)
        # Resolve {{var_name}} to JMeter standard variable reference ${var_name}
        val = re.sub(r"\{\{([^}]+)\}\}", r"${\1}", val)
        return val
    elif isinstance(val, dict):
        return {k: translate_placeholders(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [translate_placeholders(v) for v in val]
    return val

def parse_url(url_str):
    """
    Splits a base_url or relative endpoint to get protocol, host, port, path.
    """
    parsed = urllib.parse.urlparse(url_str)
    protocol = parsed.scheme or "http"
    netloc = parsed.netloc
    if ":" in netloc:
        host, port = netloc.split(":", 1)
    else:
        host = netloc
        port = ""
    path = parsed.path
    return protocol, host, port, path

def get_sampler_url_details(endpoint, default_protocol, default_host, default_port):
    """
    Retrieves the protocol, host, port, and path for an individual test case endpoint.
    If the endpoint is a full URL, it overrides the defaults.
    """
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return parse_url(endpoint)
    else:
        path = endpoint
        if not path.startswith("/"):
            path = "/" + path
        return default_protocol, default_host, default_port, path

def add_element_with_hash_tree(parent_hash_tree, element, children_builder_fn=None):
    """
    Helper to construct JMeter's nested hashTree structure correctly.
    Every element in a JMX is paired with an immediately following <hashTree>.
    """
    parent_hash_tree.append(element)
    child_hash_tree = ET.Element("hashTree")
    parent_hash_tree.append(child_hash_tree)
    if children_builder_fn:
        children_builder_fn(child_hash_tree)
    return element, child_hash_tree

def indent_xml(elem, level=0):
    """
    Recursive helper to pretty-print XML trees in place.
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for sub_elem in elem:
            indent_xml(sub_elem, level + 1)
        if not sub_elem.tail or not sub_elem.tail.strip():
            sub_elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def guess_mime_type(file_path):
    """
    Guesses content type of a file based on file path extension.
    """
    guessed, _ = mimetypes.guess_type(file_path)
    return guessed or "application/octet-stream"

def build_status_code_assertion(expected):
    """
    Response Assertion verifying status code.
    """
    assertion = ET.Element("ResponseAssertion", guiclass="AssertionGui", testclass="ResponseAssertion", testname="Status Code Assertion", enabled="true")
    
    test_field = ET.SubElement(assertion, "stringProp", name="Assertion.test_field")
    test_field.text = "Assertion.response_code"
    
    assume_success = ET.SubElement(assertion, "boolProp", name="Assertion.assume_success")
    assume_success.text = "true"
    
    test_type = ET.SubElement(assertion, "intProp", name="Assertion.test_type")
    test_type.text = "8"  # 8 is EQUALS
    
    test_strings = ET.SubElement(assertion, "collectionProp", name="Asserion.test_strings")
    str_prop = ET.SubElement(test_strings, "stringProp", name=str(hash(expected)))
    str_prop.text = str(expected)
    
    custom_message = ET.SubElement(assertion, "stringProp", name="Assertion.custom_message")
    custom_message.text = ""
    
    return assertion

def build_duration_assertion(expected):
    """
    Duration Assertion verifying response time.
    """
    assertion = ET.Element("DurationAssertion", guiclass="DurationAssertionGui", testclass="DurationAssertion", testname="Response Time Assertion", enabled="true")
    duration = ET.SubElement(assertion, "stringProp", name="DurationAssertion.duration")
    duration.text = str(expected)
    return assertion

def build_body_contains_assertion(expected):
    """
    Response Assertion verifying substring match in response body.
    """
    assertion = ET.Element("ResponseAssertion", guiclass="AssertionGui", testclass="ResponseAssertion", testname="Body Contains Assertion", enabled="true")
    
    test_field = ET.SubElement(assertion, "stringProp", name="Assertion.test_field")
    test_field.text = "Assertion.response_data"
    
    assume_success = ET.SubElement(assertion, "boolProp", name="Assertion.assume_success")
    assume_success.text = "false"
    
    test_type = ET.SubElement(assertion, "intProp", name="Assertion.test_type")
    test_type.text = "2"  # 2 is CONTAINS
    
    test_strings = ET.SubElement(assertion, "collectionProp", name="Asserion.test_strings")
    str_prop = ET.SubElement(test_strings, "stringProp", name=str(hash(expected)))
    str_prop.text = str(expected)
    
    custom_message = ET.SubElement(assertion, "stringProp", name="Assertion.custom_message")
    custom_message.text = ""
    
    return assertion

def build_header_contains_assertion(header_name, expected):
    """
    JSR223 Groovy Assertion verifying a specific header matches the expected substring.
    """
    assertion = ET.Element("JSR223Assertion", guiclass="TestBeanGUI", testclass="JSR223Assertion", testname=f"Header '{header_name}' Contains Assertion", enabled="true")
    
    ET.SubElement(assertion, "stringProp", name="cacheKey").text = "true"
    ET.SubElement(assertion, "stringProp", name="filename").text = ""
    ET.SubElement(assertion, "stringProp", name="parameters").text = ""
    ET.SubElement(assertion, "stringProp", name="scriptLanguage").text = "groovy"
    
    escaped_header = header_name.replace('"', '\\"')
    escaped_expected = str(expected).replace('"', '\\"')
    
    script_code = f"""
def headerVal = prev.getResponseHeaders().split("\\n").find {{ it.toLowerCase().startsWith("{escaped_header.lower()}:") }}
if (headerVal == null || !headerVal.toLowerCase().contains("{escaped_expected.lower()}")) {{
    AssertionResult.setFailure(true)
    AssertionResult.setFailureMessage("Header '{escaped_header}' not found or does not contain '{escaped_expected}'")
}}
"""
    ET.SubElement(assertion, "stringProp", name="script").text = script_code.strip()
    return assertion

def build_json_path_exists_assertion(path):
    """
    JSON Path Assertion verifying the path is present.
    """
    assertion = ET.Element("JSONPathAssertion", guiclass="JSONPathAssertionGui", testclass="JSONPathAssertion", testname=f"JSON Path '{path}' Exists", enabled="true")
    ET.SubElement(assertion, "stringProp", name="JSON_PATH").text = path
    ET.SubElement(assertion, "stringProp", name="EXPECTED_VALUE").text = ""
    ET.SubElement(assertion, "boolProp", name="JSONVALIDATION").text = "false"
    ET.SubElement(assertion, "boolProp", name="EXPECT_NULL").text = "false"
    ET.SubElement(assertion, "boolProp", name="INVERT").text = "false"
    ET.SubElement(assertion, "boolProp", name="ISREGEX").text = "true"
    return assertion

def build_json_path_equals_assertion(path, expected):
    """
    JSON Path Assertion verifying the value at path equals expected value.
    """
    assertion = ET.Element("JSONPathAssertion", guiclass="JSONPathAssertionGui", testclass="JSONPathAssertion", testname=f"JSON Path '{path}' Equals '{expected}'", enabled="true")
    ET.SubElement(assertion, "stringProp", name="JSON_PATH").text = path
    ET.SubElement(assertion, "stringProp", name="EXPECTED_VALUE").text = str(expected) if expected is not None else ""
    ET.SubElement(assertion, "boolProp", name="JSONVALIDATION").text = "true"
    ET.SubElement(assertion, "boolProp", name="EXPECT_NULL").text = "true" if expected is None else "false"
    ET.SubElement(assertion, "boolProp", name="INVERT").text = "false"
    ET.SubElement(assertion, "boolProp", name="ISREGEX").text = "false"
    return assertion

def build_json_path_contains_assertion(path, expected):
    """
    JSON Path Assertion verifying the value contains expected string (using regex match).
    """
    assertion = ET.Element("JSONPathAssertion", guiclass="JSONPathAssertionGui", testclass="JSONPathAssertion", testname=f"JSON Path '{path}' Contains '{expected}'", enabled="true")
    ET.SubElement(assertion, "stringProp", name="JSON_PATH").text = path
    
    escaped_expected = re.escape(str(expected))
    ET.SubElement(assertion, "stringProp", name="EXPECTED_VALUE").text = f".*{escaped_expected}.*"
    ET.SubElement(assertion, "boolProp", name="JSONVALIDATION").text = "true"
    ET.SubElement(assertion, "boolProp", name="EXPECT_NULL").text = "false"
    ET.SubElement(assertion, "boolProp", name="INVERT").text = "false"
    ET.SubElement(assertion, "boolProp", name="ISREGEX").text = "true"
    return assertion

def build_json_path_type_assertion(path, expected_type):
    """
    JSR223 Groovy Assertion parsing the JSON and evaluating the type of value at path.
    """
    assertion = ET.Element("JSR223Assertion", guiclass="TestBeanGUI", testclass="JSR223Assertion", testname=f"JSON Path '{path}' Type is '{expected_type}'", enabled="true")
    
    ET.SubElement(assertion, "stringProp", name="cacheKey").text = "true"
    ET.SubElement(assertion, "stringProp", name="filename").text = ""
    ET.SubElement(assertion, "stringProp", name="parameters").text = ""
    ET.SubElement(assertion, "stringProp", name="scriptLanguage").text = "groovy"
    
    escaped_path = path.replace('"', '\\"')
    escaped_type = expected_type.replace('"', '\\"')
    
    script_code = f"""
import groovy.json.JsonSlurper
def jsonStr = prev.getResponseDataAsString()
try {{
    def json = new JsonSlurper().parseText(jsonStr)
    def path = "{escaped_path}"
    def expectedType = "{escaped_type}"
    
    def tokens = []
    def matcher = (path =~ /\\.([A-Za-z0-9_-]+)|\\[(\\d+)\\]/)
    while (matcher.find()) {{
        if (matcher.group(1) != null) {{
            tokens.add([type: 'key', value: matcher.group(1)])
        }} else {{
            tokens.add([type: 'index', value: matcher.group(2).toInteger()])
        }}
    }}
    
    def current = json
    def found = true
    for (token in tokens) {{
        if (current == null) {{ found = false; break; }}
        if (token.type == 'index') {{
            int idx = token.value
            if (current instanceof List && idx >= 0 && idx < current.size()) {{
                current = current[idx]
            }} else {{
                found = false
                break
            }}
        }} else {{
            def key = token.value
            if (current instanceof Map && current.containsKey(key)) {{
                current = current[key]
            }} else {{
                found = false
                break
            }}
        }}
    }}
    
    if (!found) {{
        AssertionResult.setFailure(true)
        AssertionResult.setFailureMessage("Path " + path + " not found in JSON response")
    }} else {{
        def typeName = "unknown"
        if (current == null) typeName = "null"
        else if (current instanceof Boolean) typeName = "boolean"
        else if (current instanceof Integer) typeName = "integer"
        else if (current instanceof Number) typeName = "number"
        else if (current instanceof String) typeName = "string"
        else if (current instanceof List) typeName = "array"
        else if (current instanceof Map) typeName = "object"
        
        if (typeName != expectedType) {{
            AssertionResult.setFailure(true)
            AssertionResult.setFailureMessage("Expected type for path " + path + " to be " + expectedType + ", but got " + typeName + " (value: " + current + ")")
        }}
    }}
}} catch (Exception e) {{
    AssertionResult.setFailure(true)
    AssertionResult.setFailureMessage("Failed to parse response or evaluate JSON Path type check: " + e.getMessage())
}}
"""
    ET.SubElement(assertion, "stringProp", name="script").text = script_code.strip()
    return assertion

def build_json_extractor(ref_name, json_path):
    """
    JSON PostProcessor extracting response value to a variable.
    """
    extractor = ET.Element("JSONPostProcessor", guiclass="JSONPostProcessorGui", testclass="JSONPostProcessor", testname=f"Extract variable '{ref_name}'", enabled="true")
    ET.SubElement(extractor, "stringProp", name="JSONPostProcessor.referenceNames").text = ref_name
    ET.SubElement(extractor, "stringProp", name="JSONPostProcessor.jsonPathExprs").text = json_path
    ET.SubElement(extractor, "stringProp", name="JSONPostProcessor.match_numbers").text = "1"
    ET.SubElement(extractor, "stringProp", name="JSONPostProcessor.defaultValues").text = "NV"
    return extractor

def build_http_sampler(case, default_protocol, default_host, default_port):
    """
    Builds the main HTTPSamplerProxy for a case.
    """
    endpoint = translate_placeholders(case.get("endpoint", ""))
    protocol, host, port, path = get_sampler_url_details(endpoint, default_protocol, default_host, default_port)
    
    method = case.get("method", "GET").upper()
    testname = case.get("name", case.get("id", "HTTP Request"))
    
    sampler = ET.Element("HTTPSamplerProxy", guiclass="HttpTestSampleGui", testclass="HTTPSamplerProxy", testname=testname, enabled="true")
    
    ET.SubElement(sampler, "stringProp", name="HTTPSampler.domain").text = host
    ET.SubElement(sampler, "stringProp", name="HTTPSampler.port").text = port
    ET.SubElement(sampler, "stringProp", name="HTTPSampler.protocol").text = protocol
    ET.SubElement(sampler, "stringProp", name="HTTPSampler.contentEncoding").text = "UTF-8"
    ET.SubElement(sampler, "stringProp", name="HTTPSampler.path").text = path
    ET.SubElement(sampler, "stringProp", name="HTTPSampler.method").text = method
    ET.SubElement(sampler, "boolProp", name="HTTPSampler.follow_redirects").text = "true"
    ET.SubElement(sampler, "boolProp", name="HTTPSampler.auto_redirects").text = "false"
    ET.SubElement(sampler, "boolProp", name="HTTPSampler.use_keepalive").text = "true"
    
    has_files = "files" in case or "multipart" in case
    ET.SubElement(sampler, "boolProp", name="HTTPSampler.DO_MULTIPART_POST").text = "true" if has_files else "false"
    
    args_elem = ET.SubElement(sampler, "elementProp", name="HTTPsampler.Arguments", elementType="Arguments", guiclass="HTTPArgumentsPanel", testclass="Arguments", testname="User Defined Variables", enabled="true")
    collection = ET.SubElement(args_elem, "collectionProp", name="Arguments.arguments")
    
    is_raw_body = False
    
    if "json" in case:
        is_raw_body = True
        ET.SubElement(sampler, "boolProp", name="HTTPSampler.postBodyRaw").text = "true"
        arg = ET.SubElement(collection, "elementProp", name="", elementType="HTTPArgument")
        ET.SubElement(arg, "boolProp", name="HTTPArgument.always_encode").text = "false"
        
        json_str = json.dumps(case["json"], indent=2)
        translated_json = translate_placeholders(json_str)
        ET.SubElement(arg, "stringProp", name="Argument.value").text = translated_json
        ET.SubElement(arg, "stringProp", name="Argument.metadata").text = "="
        
    elif "body" in case:
        is_raw_body = True
        ET.SubElement(sampler, "boolProp", name="HTTPSampler.postBodyRaw").text = "true"
        arg = ET.SubElement(collection, "elementProp", name="", elementType="HTTPArgument")
        ET.SubElement(arg, "boolProp", name="HTTPArgument.always_encode").text = "false"
        
        body_val = translate_placeholders(case["body"])
        ET.SubElement(arg, "stringProp", name="Argument.value").text = body_val
        ET.SubElement(arg, "stringProp", name="Argument.metadata").text = "="
        
    elif "form" in case:
        ET.SubElement(sampler, "boolProp", name="HTTPSampler.postBodyRaw").text = "false"
        form_data = case["form"]
        for k, v in form_data.items():
            translated_k = translate_placeholders(k)
            translated_v = translate_placeholders(v)
            arg = ET.SubElement(collection, "elementProp", name=translated_k, elementType="HTTPArgument")
            ET.SubElement(arg, "boolProp", name="HTTPArgument.always_encode").text = "true"
            ET.SubElement(arg, "stringProp", name="Argument.value").text = str(translated_v)
            ET.SubElement(arg, "stringProp", name="Argument.metadata").text = "="
            ET.SubElement(arg, "boolProp", name="HTTPArgument.use_equals").text = "true"
            ET.SubElement(arg, "stringProp", name="Argument.name").text = translated_k
            
    elif "multipart" in case:
        ET.SubElement(sampler, "boolProp", name="HTTPSampler.postBodyRaw").text = "false"
        multipart_data = case["multipart"]
        for k, v in multipart_data.items():
            translated_k = translate_placeholders(k)
            translated_v = translate_placeholders(v)
            arg = ET.SubElement(collection, "elementProp", name=translated_k, elementType="HTTPArgument")
            ET.SubElement(arg, "boolProp", name="HTTPArgument.always_encode").text = "false"
            ET.SubElement(arg, "stringProp", name="Argument.value").text = str(translated_v)
            ET.SubElement(arg, "stringProp", name="Argument.metadata").text = "="
            ET.SubElement(arg, "boolProp", name="HTTPArgument.use_equals").text = "true"
            ET.SubElement(arg, "stringProp", name="Argument.name").text = translated_k

    if not is_raw_body:
        ET.SubElement(sampler, "boolProp", name="HTTPSampler.postBodyRaw").text = "false"
        
    if "files" in case:
        files_elem = ET.SubElement(sampler, "elementProp", name="HTTPsampler.Files", elementType="HTTPFileArgs")
        files_collection = ET.SubElement(files_elem, "collectionProp", name="HTTPFileArgs.files")
        for param_name, file_info in case["files"].items():
            translated_param = translate_placeholders(param_name)
            if isinstance(file_info, str):
                file_path = translate_placeholders(file_info)
                mime_type = guess_mime_type(file_path)
            elif isinstance(file_info, dict):
                file_path = translate_placeholders(file_info.get("path", ""))
                mime_type = translate_placeholders(file_info.get("content_type", guess_mime_type(file_path)))
            else:
                continue
                
            file_arg = ET.SubElement(files_collection, "elementProp", name=file_path, elementType="HTTPFileArg")
            ET.SubElement(file_arg, "stringProp", name="File.path").text = file_path
            ET.SubElement(file_arg, "stringProp", name="File.paramname").text = translated_param
            ET.SubElement(file_arg, "stringProp", name="File.mimetype").text = mime_type

    return sampler

def build_header_manager(case):
    """
    Builds the HTTP Header Manager for a case, auto-calculating headers as appropriate.
    """
    headers = case.get("headers", {}).copy()
    
    if "json" in case:
        has_content_type = any(k.lower() == "content-type" for k in headers.keys())
        if not has_content_type:
            headers["Content-Type"] = "application/json"
            
    if "form" in case:
        has_content_type = any(k.lower() == "content-type" for k in headers.keys())
        if not has_content_type:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
    if "files" in case or "multipart" in case:
        # Strip Content-Type so JMeter auto-calculates boundary
        headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
        
    if not headers:
        return None
        
    manager = ET.Element("HeaderManager", guiclass="HeaderPanel", testclass="HeaderManager", testname="HTTP Header Manager", enabled="true")
    collection = ET.SubElement(manager, "collectionProp", name="HeaderManager.headers")
    
    for k, v in headers.items():
        translated_k = translate_placeholders(k)
        translated_v = translate_placeholders(v)
        arg = ET.SubElement(collection, "elementProp", name="", elementType="Header")
        ET.SubElement(arg, "stringProp", name="Header.name").text = translated_k
        ET.SubElement(arg, "stringProp", name="Header.value").text = translated_v
        
    return manager

def build_extractors(case):
    extractors = []
    extract = case.get("extract", {})
    for var_name, json_path in extract.items():
        extractor = build_json_extractor(var_name, json_path)
        extractors.append(extractor)
    return extractors

def build_assertions(case):
    assertions_elements = []
    assertions = case.get("assertions", [])
    for assertion in assertions:
        kind = assertion.get("type")
        expected = assertion.get("expected")
        path = assertion.get("path")
        
        if kind == "status_code":
            assertions_elements.append(build_status_code_assertion(expected))
        elif kind == "response_time_under_ms":
            assertions_elements.append(build_duration_assertion(expected))
        elif kind == "header_contains":
            header_name = assertion.get("header", "")
            assertions_elements.append(build_header_contains_assertion(header_name, expected))
        elif kind == "body_contains":
            assertions_elements.append(build_body_contains_assertion(expected))
        elif kind == "json_path_exists":
            assertions_elements.append(build_json_path_exists_assertion(path))
        elif kind == "json_path_equals":
            assertions_elements.append(build_json_path_equals_assertion(path, expected))
        elif kind == "json_path_contains":
            assertions_elements.append(build_json_path_contains_assertion(path, expected))
        elif kind == "json_path_type":
            assertions_elements.append(build_json_path_type_assertion(path, expected))
            
    return assertions_elements

def generate_jmx(suite_data):
    """
    Core function orchestrating the JMX structure building.
    """
    jmeter_test_plan = ET.Element("jmeterTestPlan", version="1.2", properties="5.0", jmeter="5.5")
    
    root_hash_tree = ET.Element("hashTree")
    jmeter_test_plan.append(root_hash_tree)
    
    base_url = suite_data.get("base_url", "")
    default_protocol, default_host, default_port, default_path = parse_url(base_url)
    
    suite_name = suite_data.get("name", "API Automation Suite")
    test_plan = ET.Element("TestPlan", guiclass="TestPlanGui", testclass="TestPlan", testname=suite_name, enabled="true")
    ET.SubElement(test_plan, "stringProp", name="TestPlan.comments").text = ""
    ET.SubElement(test_plan, "boolProp", name="TestPlan.functional_mode").text = "false"
    ET.SubElement(test_plan, "boolProp", name="TestPlan.tearDown_on_shutdown").text = "true"
    ET.SubElement(test_plan, "boolProp", name="TestPlan.serialize_threadgroups").text = "false"
    
    udv = ET.SubElement(test_plan, "elementProp", name="TestPlan.user_defined_variables", elementType="Arguments", guiclass="ArgumentsPanel", testclass="Arguments", testname="User Defined Variables", enabled="true")
    udv_collection = ET.SubElement(udv, "collectionProp", name="Arguments.arguments")
    
    env_name = suite_data.get("environment", "")
    if env_name:
        env_arg = ET.SubElement(udv_collection, "elementProp", name="environment", elementType="Argument")
        ET.SubElement(env_arg, "stringProp", name="Argument.name").text = "environment"
        ET.SubElement(env_arg, "stringProp", name="Argument.value").text = env_name
        ET.SubElement(env_arg, "stringProp", name="Argument.metadata").text = "="
        
    ET.SubElement(test_plan, "stringProp", name="TestPlan.user_define_classpath").text = ""
    
    _, tp_hash_tree = add_element_with_hash_tree(root_hash_tree, test_plan)
    
    timeout_secs = float(suite_data.get("timeout_seconds", 10))
    timeout_ms = str(int(timeout_secs * 1000))
    
    defaults_elem = ET.Element("ConfigTestElement", guiclass="HttpDefaultsGui", testclass="ConfigTestElement", testname="HTTP Request Defaults", enabled="true")
    ET.SubElement(defaults_elem, "stringProp", name="HTTPSampler.domain").text = default_host
    ET.SubElement(defaults_elem, "stringProp", name="HTTPSampler.port").text = default_port
    ET.SubElement(defaults_elem, "stringProp", name="HTTPSampler.protocol").text = default_protocol
    ET.SubElement(defaults_elem, "stringProp", name="HTTPSampler.contentEncoding").text = "UTF-8"
    ET.SubElement(defaults_elem, "stringProp", name="HTTPSampler.path").text = default_path
    ET.SubElement(defaults_elem, "stringProp", name="HTTPSampler.connect_timeout").text = timeout_ms
    ET.SubElement(defaults_elem, "stringProp", name="HTTPSampler.response_timeout").text = timeout_ms
    
    def_args = ET.SubElement(defaults_elem, "elementProp", name="HTTPsampler.Arguments", elementType="Arguments", guiclass="HTTPArgumentsPanel", testclass="Arguments", testname="User Defined Variables", enabled="true")
    ET.SubElement(def_args, "collectionProp", name="Arguments.arguments")
    
    add_element_with_hash_tree(tp_hash_tree, defaults_elem)
    
    cookie_manager = ET.Element("CookieManager", guiclass="CookiePanel", testclass="CookieManager", testname="HTTP Cookie Manager", enabled="true")
    ET.SubElement(cookie_manager, "collectionProp", name="CookieManager.cookies")
    ET.SubElement(cookie_manager, "boolProp", name="CookieManager.clearEachIteration").text = "true"
    ET.SubElement(cookie_manager, "boolProp", name="CookieManager.controlledByThread").text = "false"
    
    add_element_with_hash_tree(tp_hash_tree, cookie_manager)
    
    thread_group = ET.Element("ThreadGroup", guiclass="ThreadGroupGui", testclass="ThreadGroup", testname="Thread Group", enabled="true")
    ET.SubElement(thread_group, "stringProp", name="ThreadGroup.on_sample_error").text = "continue"
    
    loop_ctrl = ET.SubElement(thread_group, "elementProp", name="ThreadGroup.main_controller", elementType="LoopController", guiclass="LoopControlPanel", testclass="LoopController", testname="Loop Controller", enabled="true")
    ET.SubElement(loop_ctrl, "boolProp", name="LoopController.continue_forever").text = "false"
    ET.SubElement(loop_ctrl, "stringProp", name="LoopController.loops").text = "1"
    
    ET.SubElement(thread_group, "stringProp", name="ThreadGroup.num_threads").text = "1"
    ET.SubElement(thread_group, "stringProp", name="ThreadGroup.ramp_time").text = "1"
    ET.SubElement(thread_group, "boolProp", name="ThreadGroup.scheduler").text = "false"
    ET.SubElement(thread_group, "stringProp", name="ThreadGroup.duration").text = ""
    ET.SubElement(thread_group, "stringProp", name="ThreadGroup.delay").text = ""
    ET.SubElement(thread_group, "boolProp", name="ThreadGroup.same_user_on_next_iteration").text = "true"
    
    def build_thread_group_children(tg_hash_tree):
        view_results_tree = ET.Element("ResultCollector", guiclass="ViewResultsFullVisualizer", testclass="ResultCollector", testname="View Results Tree", enabled="true")
        ET.SubElement(view_results_tree, "boolProp", name="ResultCollector.error_logging").text = "false"
        obj_prop = ET.SubElement(view_results_tree, "objProp")
        ET.SubElement(obj_prop, "name").text = "saveConfig"
        save_config = ET.SubElement(obj_prop, "value", attrib={"class": "SampleSaveConfiguration"})
        fields = {
            "time": "true",
            "latency": "true",
            "timestamp": "true",
            "success": "true",
            "label": "true",
            "code": "true",
            "message": "true",
            "threadName": "true",
            "dataType": "true",
            "encoding": "false",
            "assertions": "true",
            "subresults": "true",
            "responseData": "false",
            "samplerData": "false",
            "xml": "false",
            "fieldNames": "true",
            "responseHeaders": "false",
            "requestHeaders": "false",
            "responseDataOnError": "false",
            "saveAssertionResultsFailureMessage": "true",
            "bytes": "true",
            "sentBytes": "true",
            "url": "true",
            "threadCounts": "true",
            "idleTime": "true",
            "connectTime": "true"
        }
        for field, val in fields.items():
            ET.SubElement(save_config, field).text = val
        
        ET.SubElement(view_results_tree, "stringProp", name="filename").text = ""
        add_element_with_hash_tree(tg_hash_tree, view_results_tree)
        
        defaults_suite = suite_data.get("defaults", {})
        cases = suite_data.get("cases", [])
        
        for case in cases:
            repeat = int(case.get("repeat", defaults_suite.get("repeat", 1)))
            
            def add_case_sampler(target_hash_tree):
                sampler = build_http_sampler(case, default_protocol, default_host, default_port)
                
                def build_sampler_children(sampler_hash_tree):
                    headers_elem = build_header_manager(case)
                    if headers_elem is not None:
                        add_element_with_hash_tree(sampler_hash_tree, headers_elem)
                    
                    extractors = build_extractors(case)
                    for extractor in extractors:
                        add_element_with_hash_tree(sampler_hash_tree, extractor)
                        
                    assertions = build_assertions(case)
                    for assertion in assertions:
                        add_element_with_hash_tree(sampler_hash_tree, assertion)
                
                add_element_with_hash_tree(target_hash_tree, sampler, build_sampler_children)
            
            if repeat > 1:
                case_loop = ET.Element("LoopController", guiclass="LoopControlPanel", testclass="LoopController", testname=f"Loop - {case.get('name', case.get('id', 'Case'))}", enabled="true")
                ET.SubElement(case_loop, "boolProp", name="LoopController.continue_forever").text = "false"
                ET.SubElement(case_loop, "stringProp", name="LoopController.loops").text = str(repeat)
                
                def build_loop_children(loop_hash_tree):
                    add_case_sampler(loop_hash_tree)
                    
                add_element_with_hash_tree(tg_hash_tree, case_loop, build_loop_children)
            else:
                add_case_sampler(tg_hash_tree)
                
    add_element_with_hash_tree(tp_hash_tree, thread_group, build_thread_group_children)
    
    indent_xml(jmeter_test_plan)
    
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content = ET.tostring(jmeter_test_plan, encoding="utf-8").decode("utf-8")
    
    return xml_declaration + xml_content

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Convert API Automation Suite JSON to JMeter JMX format.")
    parser.add_argument("json_file", help="Path to the input suite JSON file.")
    parser.add_argument("-o", "--output", help="Path to the output JMX file. Defaults to replacing .json with .jmx.")
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
        output_path = base + ".jmx"
        
    try:
        jmx_content = generate_jmx(suite_data)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(jmx_content)
        print(f"Successfully converted '{args.json_file}' to '{output_path}'")
    except Exception as e:
        import traceback
        print(f"Conversion failed: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
