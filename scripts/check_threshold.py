"""Check that evaluation metric thresholds are met after pytest runs.

This script is called by the CI pipeline after ``pytest tests/evaluation``
completes.  Because the evaluation tests already enforce metric thresholds
internally (95% for tool_selection, 100% for refusal_accuracy), this script
acts as a second gate by reading the JUnit XML report that pytest produces.

Usage
-----
    python scripts/check_threshold.py --metric tool_selection --threshold 0.95
    python scripts/check_threshold.py --metric refusal_accuracy --threshold 1.0

Exit codes
----------
0   All evaluation tests in the relevant suite passed (threshold met).
1   One or more failures detected in the evaluation XML (threshold not met).

If the JUnit XML file does not exist this script exits 0 and prints a warning,
on the assumption that pytest itself already gated the pipeline before reaching
this step.
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EVALUATION_XML: Path = Path("test-results/evaluation.xml")

VALID_METRICS: frozenset[str] = frozenset({"tool_selection", "refusal_accuracy"})


def _parse_args() -> argparse.Namespace:
    """Parse and validate CLI arguments.

    Returns:
        Parsed namespace with ``metric`` (str) and ``threshold`` (float).
    """
    parser = argparse.ArgumentParser(
        description="Verify that an evaluation metric threshold is met.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/check_threshold.py --metric tool_selection --threshold 0.95\n"
            "  python scripts/check_threshold.py --metric refusal_accuracy --threshold 1.0\n"
        ),
    )
    parser.add_argument(
        "--metric",
        required=True,
        choices=sorted(VALID_METRICS),
        help="Name of the evaluation metric to check.",
    )
    parser.add_argument(
        "--threshold",
        required=True,
        type=float,
        help="Minimum acceptable pass rate in the range [0.0, 1.0].",
    )
    args = parser.parse_args()

    if not 0.0 <= args.threshold <= 1.0:
        parser.error(f"--threshold must be between 0.0 and 1.0, got {args.threshold}")

    return args


def _count_failures(xml_path: Path) -> tuple[int, int]:
    """Parse a JUnit XML file and return (total_tests, total_failures).

    The JUnit schema produced by pytest places test counts on the root
    ``<testsuites>`` element or directly on each ``<testsuite>`` child.
    Both layouts are handled.

    Args:
        xml_path: Path to the JUnit XML file to parse.

    Returns:
        A tuple of (total_tests, total_failures).  Errors are counted as
        failures because they also prevent a test from passing.

    Raises:
        ValueError: If the XML cannot be parsed or has an unexpected schema.
    """
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        raise ValueError(f"Cannot parse {xml_path}: {exc}") from exc

    root = tree.getroot()

    total_tests: int = 0
    total_failures: int = 0

    # The root may be <testsuites> (wrapping multiple <testsuite> elements)
    # or a single <testsuite> element directly.
    if root.tag == "testsuites":
        suites = root.findall("testsuite")
    elif root.tag == "testsuite":
        suites = [root]
    else:
        raise ValueError(
            f"Unexpected root element <{root.tag}> in {xml_path}. "
            "Expected <testsuites> or <testsuite>."
        )

    for suite in suites:
        tests_attr = suite.get("tests", "0")
        failures_attr = suite.get("failures", "0")
        errors_attr = suite.get("errors", "0")

        try:
            total_tests += int(tests_attr)
            total_failures += int(failures_attr) + int(errors_attr)
        except ValueError:
            # Malformed attributes — count each <failure> and <error> tag
            # inside the suite as a fallback.
            for case in suite.findall("testcase"):
                total_tests += 1
                if case.find("failure") is not None or case.find("error") is not None:
                    total_failures += 1

    return total_tests, total_failures


def main() -> None:
    """Entry point: parse args, read XML, assert threshold, exit accordingly."""
    args = _parse_args()
    metric: str = args.metric
    threshold: float = args.threshold

    if not EVALUATION_XML.exists():
        print(
            f"[check_threshold] WARNING: {EVALUATION_XML} not found. "
            "Assuming pytest already enforced the threshold. Exiting 0."
        )
        sys.exit(0)

    try:
        total, failures = _count_failures(EVALUATION_XML)
    except ValueError as exc:
        print(f"[check_threshold] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if total == 0:
        print(
            f"[check_threshold] WARNING: No tests found in {EVALUATION_XML}. "
            "Exiting 0."
        )
        sys.exit(0)

    passed = total - failures
    actual_rate: float = passed / total

    status_line = (
        f"[check_threshold] metric={metric} "
        f"passed={passed}/{total} ({actual_rate:.1%}) "
        f"threshold={threshold:.1%}"
    )
    print(status_line)

    if failures > 0:
        print(
            f"[check_threshold] FAIL: {failures} test(s) failed — "
            f"metric '{metric}' did not meet threshold {threshold:.1%}.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[check_threshold] PASS: metric '{metric}' threshold {threshold:.1%} met.")
    sys.exit(0)


if __name__ == "__main__":
    main()
