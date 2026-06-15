import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .assertions import evaluate_assertions
from .client import ApiClient
from .metrics import timing_summary
from .report import write_html_report


def _interpolate(val: Any, variables: Dict[str, Any]) -> Any:
    if isinstance(val, str):
        result = val
        for k, v in variables.items():
            placeholder = f"{{{{{k}}}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(v))
        return result
    elif isinstance(val, dict):
        return {k: _interpolate(v, variables) for k, v in val.items()}
    elif isinstance(val, list):
        return [_interpolate(v, variables) for v in val]
    return val


def load_suite(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_suite(suite_path: Path, output_dir: Path) -> Path:
    suite = load_suite(suite_path)
    client = ApiClient(
        base_url=suite.get("base_url", ""),
        timeout_seconds=float(suite.get("timeout_seconds", 10)),
        verify_ssl=bool(suite.get("verify_ssl", True)),
    )
    defaults = suite.get("defaults", {})
    case_results = []
    variables = {}

    for case in suite.get("cases", []):
        case_results.append(_run_case(client, defaults, case, variables))

    summary = _summarize(case_results)
    run = {
        "suite_name": suite.get("name", suite_path.stem),
        "environment": suite.get("environment", "local"),
        "base_url": suite.get("base_url", ""),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "summary": summary,
        "cases": case_results,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"api_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    write_html_report(run, report_path)
    return report_path


def run_suite_with_result(suite_path: Path, output_dir: Path) -> Dict[str, Any]:
    suite = load_suite(suite_path)
    client = ApiClient(
        base_url=suite.get("base_url", ""),
        timeout_seconds=float(suite.get("timeout_seconds", 10)),
        verify_ssl=bool(suite.get("verify_ssl", True)),
    )
    defaults = suite.get("defaults", {})
    case_results = []
    variables = {}

    for case in suite.get("cases", []):
        case_results.append(_run_case(client, defaults, case, variables))

    summary = _summarize(case_results)
    run = {
        "suite_name": suite.get("name", suite_path.stem),
        "environment": suite.get("environment", "local"),
        "base_url": suite.get("base_url", ""),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "summary": summary,
        "cases": case_results,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"api_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    write_html_report(run, report_path)
    run["report_path"] = report_path
    return run


def _run_case(client: ApiClient, defaults: Dict[str, Any], case: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    repeat = int(case.get("repeat", defaults.get("repeat", 1)))
    min_success_rate = float(case.get("min_success_rate", defaults.get("min_success_rate", 100)))
    max_p95_ms = case.get("max_p95_ms", defaults.get("max_p95_ms"))

    iterations = []
    for index in range(repeat):
        interpolated_case = copy.deepcopy(case)
        interpolated_case = _interpolate(interpolated_case, variables)

        response = client.send(interpolated_case)

        # Extract variables from response if successful
        if response["error"] is None and "extract" in case:
            from .assertions import extract_json_path
            for var_name, json_path in case["extract"].items():
                found, val = extract_json_path(response.get("json"), json_path)
                if found:
                    variables[var_name] = val

        # Re-interpolate case fields/assertions if they depend on variables extracted *during* this case's runs
        interpolated_case = _interpolate(interpolated_case, variables)
        iter_assertions = interpolated_case.get("assertions", [])
        assertion_results = evaluate_assertions(response, iter_assertions, response["elapsed_ms"])
        passed = response["error"] is None and all(item["passed"] for item in assertion_results)
        iterations.append(
            {
                "iteration": index + 1,
                "passed": passed,
                "status_code": response["status_code"],
                "elapsed_ms": round(response["elapsed_ms"], 2),
                "error": response["error"],
                "assertions": assertion_results,
            }
        )

    timings = [item["elapsed_ms"] for item in iterations]
    metrics = timing_summary(timings)
    success_count = sum(1 for item in iterations if item["passed"])
    success_rate = round((success_count / repeat) * 100, 2) if repeat else 0
    reliability_passed = success_rate >= min_success_rate
    performance_passed = True if max_p95_ms is None else metrics["p95"] <= float(max_p95_ms)
    passed = reliability_passed and performance_passed

    return {
        "id": case.get("id", case.get("name", "unnamed")),
        "name": case.get("name", case.get("id", "Unnamed case")),
        "method": case.get("method", "GET").upper(),
        "endpoint": case.get("endpoint", ""),
        "repeat": repeat,
        "success_rate": success_rate,
        "min_success_rate": min_success_rate,
        "max_p95_ms": max_p95_ms,
        "timings": metrics,
        "reliability_passed": reliability_passed,
        "performance_passed": performance_passed,
        "passed": passed,
        "iterations": iterations,
    }


def _summarize(case_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(case_results)
    passed = sum(1 for case in case_results if case["passed"])
    failed = total - passed
    all_timings = []
    for case in case_results:
        all_timings.extend(item["elapsed_ms"] for item in case["iterations"])
    timings = timing_summary(all_timings)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round((passed / total) * 100, 2) if total else 0,
        "timings": timings,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run API automation suite and create HTML report.")
    parser.add_argument("--suite", default="suites/sample_suite.json", help="Path to suite JSON file.")
    parser.add_argument("--out", default="reports", help="Directory for generated HTML reports.")
    args = parser.parse_args()

    run = run_suite_with_result(Path(args.suite), Path(args.out))
    report_path = run["report_path"]
    print(f"HTML report generated: {os.path.abspath(report_path)}")
    if run["summary"]["failed"]:
        print(f"API checks failed: {run['summary']['failed']} of {run['summary']['total']} cases failed.")
        return 1
    print(f"API checks passed: {run['summary']['passed']} of {run['summary']['total']} cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
