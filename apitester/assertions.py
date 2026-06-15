import json
import re
from typing import Any, Dict, List, Tuple


def extract_json_path(data: Any, path: str) -> Tuple[bool, Any]:
    if path.startswith("$") and not path.startswith("$."):
        path = "$." + path[1:]
    if not path.startswith("$."):
        return False, None

    current = data
    tokens = re.findall(r"\.([A-Za-z0-9_-]+)|\[(\d+)\]", path[1:])
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


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def evaluate_assertions(
    response: Dict[str, Any],
    assertions: List[Dict[str, Any]],
    elapsed_ms: float,
) -> List[Dict[str, Any]]:
    results = []
    json_body = response.get("json")
    text_body = response.get("body", "")
    headers = {k.lower(): v for k, v in response.get("headers", {}).items()}

    for assertion in assertions:
        kind = assertion.get("type")
        description = assertion.get("name") or _describe(assertion)
        passed = False
        actual = None
        expected = assertion.get("expected")
        message = ""

        try:
            if kind == "status_code":
                actual = response.get("status_code")
                try:
                    passed = int(actual) == int(expected)
                except (ValueError, TypeError):
                    passed = str(actual) == str(expected)
            elif kind == "response_time_under_ms":
                actual = round(elapsed_ms, 2)
                passed = elapsed_ms <= float(expected)
            elif kind == "header_contains":
                header_name = str(assertion.get("header", "")).lower()
                actual = headers.get(header_name)
                passed = actual is not None and str(expected).lower() in str(actual).lower()
            elif kind == "body_contains":
                actual = text_body
                passed = str(expected) in text_body
            elif kind == "json_path_exists":
                passed, actual = extract_json_path(json_body, assertion.get("path", ""))
            elif kind == "json_path_equals":
                found, actual = extract_json_path(json_body, assertion.get("path", ""))
                if found:
                    if str(actual) == str(expected):
                        passed = True
                    else:
                        try:
                            passed = float(actual) == float(expected)
                        except (ValueError, TypeError):
                            passed = actual == expected
            elif kind == "json_path_contains":
                found, actual = extract_json_path(json_body, assertion.get("path", ""))
                passed = found and str(expected) in str(actual)
            elif kind == "json_path_type":
                found, actual = extract_json_path(json_body, assertion.get("path", ""))
                passed = found and _type_name(actual) == expected
                actual = _type_name(actual) if found else None
            else:
                message = f"Unknown assertion type: {kind}"
        except Exception as exc:
            message = str(exc)

        if not message:
            message = "Passed" if passed else f"Expected {expected!r}, got {actual!r}"

        results.append(
            {
                "name": description,
                "type": kind,
                "passed": passed,
                "expected": expected,
                "actual": _compact(actual),
                "message": message,
            }
        )
    return results


def _describe(assertion: Dict[str, Any]) -> str:
    kind = assertion.get("type", "assertion")
    if "path" in assertion:
        return f"{kind} {assertion['path']}"
    return kind


def _compact(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)[:500]
    if isinstance(value, str):
        return value[:500]
    return value
