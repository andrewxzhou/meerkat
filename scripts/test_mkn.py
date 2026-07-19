"""MKN test suite: unit tests followed by integration tests.

Runs in two phases mirroring cargo test output:
  1. Unit tests   - manifest validation checks (no live nodes)
  2. Integration  - full orchestration tests (spawns real nodes)

Finally delegates to the lock_group integration suite for transitive
locking tests.

Run from workspace root:
    python3 scripts/test_mkn.py
"""

import subprocess
import json
import sys
import os
import signal
import time


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------

def run_cmd(args, timeout=30):
    """Run a subprocess with a timeout, merging stderr into stdout.

    Args:
        args (list[str]): Command and arguments to execute.
        timeout (int): Maximum seconds to wait before killing.

    Returns:
        tuple[int, str]: (returncode, combined output). returncode is
            -1 on timeout.
    """
    is_windows = sys.platform == "win32"
    kwargs = {}
    if is_windows:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **kwargs,
        )
        stdout, _ = proc.communicate(timeout=timeout)
        return proc.returncode, stdout
    except subprocess.TimeoutExpired:
        if is_windows:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

        stdout, _ = proc.communicate()
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        elif stdout is None:
            stdout = ""
        return -1, stdout


# ---------------------------------------------------------------------------
# Test runner primitives
# ---------------------------------------------------------------------------

def run_suite(suite_name, tests):
    """Run a list of (name, callable) tests and report cargo-style output.

    Each callable must return True on pass, False on fail.

    Args:
        suite_name (str): Human-readable label for this suite.
        tests (list[tuple[str, callable]]): Ordered list of tests.

    Returns:
        tuple[int, int]: (passed, failed) counts.
    """
    print(f"     Running scripts/test_mkn.py ({suite_name})")
    print()
    print(f"running {len(tests)} tests")

    passed = 0
    failed = 0
    start = time.monotonic()

    for name, fn in tests:
        print(f"test {name} ... ", end="", flush=True)
        try:
            ok = fn()
        except Exception as exc:
            print(f"FAILED\nerror: {exc}")
            ok = False
        if ok:
            print("ok")
            passed += 1
        else:
            failed += 1

    elapsed = time.monotonic() - start
    status = "ok" if failed == 0 else "FAILED"
    print()
    print(
        f"test result: {status}. "
        f"{passed} passed; {failed} failed; "
        f"finished in {elapsed:.2f}s"
    )
    print()
    return passed, failed


# ---------------------------------------------------------------------------
# Unit tests — manifest validation (no live nodes)
# ---------------------------------------------------------------------------

MKN = "scripts/mkn.py"
MKN_DIR = "meerkat/tests/mkn"

VALIDATION_CASES = [
    ("invalid_port",
     "test_mkn_invalid_port.json", "cannot specify a port"),
    ("missing_alias",
     "test_mkn_missing_alias.json", "missing 'alias'"),
    ("empty_nodes_list",
     "test_mkn_empty_nodes.json", "'nodes' list cannot be empty"),
    ("duplicate_alias",
     "test_mkn_duplicate_alias.json", "Duplicate node alias detected"),
    ("invalid_alias_format",
     "test_mkn_invalid_alias_format.json",
     "must match alphanumeric/underscore format"),
    ("missing_type",
     "test_mkn_missing_type.json", "missing required 'type' key"),
    ("invalid_type",
     "test_mkn_invalid_type.json", "type must be 'server' or 'client'"),
    ("missing_file_or_cmd",
     "test_mkn_missing_file_or_cmd.json",
     "must specify either 'file' or 'cmd'"),
    ("invalid_cmd",
     "test_mkn_invalid_cmd.json", "'cmd' must be a list of strings"),
    ("invalid_port_type",
     "test_mkn_invalid_port_type.json", "'port' must be an integer"),
    ("server_with_relay",
     "test_mkn_server_relay.json", "cannot specify a relay"),
    ("invalid_relay_reference",
     "test_mkn_invalid_relay.json",
     "which does not exist in the manifest"),
    ("invalid_imports_format",
     "test_mkn_invalid_imports_format.json",
     "must use 'alias.service_name' dot-notation"),
    ("invalid_imports_reference",
     "test_mkn_invalid_imports_reference.json",
     "imports from node 'missing' which does not exist"),
    ("circular_dependency",
     "test_mkn_circular_dependency.json",
     "Circular dependency detected in manifest"),
]


def make_validation_test(filename, expected_error):
    """Return a zero-argument callable for a single validation case.

    Args:
        filename (str): Manifest filename relative to MKN_DIR.
        expected_error (str): Substring expected in the error output.

    Returns:
        callable: Test function returning True on pass, False on fail.
    """
    def test():
        path = f"{MKN_DIR}/{filename}"
        code, output = run_cmd([sys.executable, MKN, path])
        if code == 0:
            print(
                f"\nFAIL: expected non-zero exit for {filename}; "
                f"got 0. Output:\n{output.strip()}"
            )
            return False
        if expected_error not in output:
            print(
                f"\nFAIL: expected '{expected_error}' in output "
                f"for {filename}. Got:\n{output.strip()}"
            )
            return False
        return True
    return test


def build_unit_tests():
    """Build the full list of unit test (name, callable) pairs.

    Returns:
        list[tuple[str, callable]]: Unit test pairs.
    """
    return [
        (name, make_validation_test(filename, expected_error))
        for name, filename, expected_error in VALIDATION_CASES
    ]


# ---------------------------------------------------------------------------
# Integration tests — full orchestration (spawns real nodes)
# ---------------------------------------------------------------------------

def test_mkn_basic_topology():
    """Verify a basic two-node server/client topology completes cleanly.

    Returns:
        bool: True if the test passed.
    """
    code, output = run_cmd(
        [sys.executable, MKN,
         f"{MKN_DIR}/test_mkn_basic.json"],
        timeout=90,
    )
    if code != 0:
        print(
            f"\nFAIL: basic topology exited {code}. "
            f"Output:\n{output.strip()}"
        )
        return False
    if "All services online." not in output:
        print(
            "\nFAIL: 'All services online.' not found in output.\n"
            + output.strip()
        )
        return False
    return True


def test_mkn_namespace_split():
    """Verify three-namespace tracking and relay routing via state dump.

    Returns:
        bool: True if the test passed.
    """
    code, output = run_cmd(
        [sys.executable, MKN,
         f"{MKN_DIR}/test_mkn_relay.json", "--dump-state"],
        timeout=90,
    )
    if code != 0:
        print(
            f"\nFAIL: namespace split exited {code}. "
            f"Output:\n{output.strip()}"
        )
        return False

    marker_start = "--- STATE DUMP ---"
    marker_end = "--- END STATE DUMP ---"
    if marker_start not in output or marker_end not in output:
        print("\nFAIL: state dump markers not found in output.")
        return False

    state_str = (
        output.split(marker_start)[1].split(marker_end)[0].strip()
    )
    try:
        state = json.loads(state_str)
    except Exception as exc:
        print(f"\nFAIL: could not parse state dump JSON: {exc}")
        return False

    relay = state.get("relay_node")
    client = state.get("relayed_client")
    if not relay or not client:
        print(
            "\nFAIL: relay_node or relayed_client missing from dump."
        )
        return False

    if "relay_svc" not in relay.get("local_services", {}):
        print("\nFAIL: relay_svc missing from relay local_services.")
        return False

    relayed = relay.get("relayed_services", {})
    if "client_svc" not in relayed:
        print(
            "\nFAIL: client_svc missing from relay relayed_services."
        )
        return False

    client_svc = relayed["client_svc"]
    if not client_svc.get("is_relayed"):
        print("\nFAIL: client_svc.is_relayed is false.")
        return False

    if client_svc.get("relay_peer_id") != relay.get("peer_id"):
        print(
            f"\nFAIL: relay_peer_id mismatch: "
            f"{client_svc.get('relay_peer_id')} != "
            f"{relay.get('peer_id')}"
        )
        return False

    if "relay_svc" not in client.get("remote_services", {}):
        print(
            "\nFAIL: relay_svc missing from client remote_services."
        )
        return False

    return True


def test_mkn_client_timeout_slow():
    """Verify a slow client that exceeds startup but not exec timeout.

    Returns:
        bool: True if the test passed.
    """
    code, output = run_cmd(
        [sys.executable, MKN,
         f"{MKN_DIR}/test_mkn_client_slow.json"],
        timeout=90,
    )
    if code != 0:
        print(
            f"\nFAIL: slow client exited {code}. "
            f"Output:\n{output.strip()}"
        )
        return False
    return True


def test_mkn_client_timeout_exec():
    """Verify a hanging client is terminated by the execution timeout.

    Returns:
        bool: True if the test passed.
    """
    code, output = run_cmd(
        [sys.executable, MKN,
         f"{MKN_DIR}/test_mkn_client_exec_timeout.json"],
        timeout=90,
    )
    if code == 0:
        print(
            "\nFAIL: hanging client exited 0; expected timeout failure."
        )
        return False
    if "execution timed out" not in output:
        print(
            "\nFAIL: 'execution timed out' not in output.\n"
            + output.strip()
        )
        return False
    return True


def test_mkn_missing_service():
    """Verify importing a missing service fails with a clear error.

    Returns:
        bool: True if the test passed.
    """
    code, output = run_cmd(
        [sys.executable, MKN,
         f"{MKN_DIR}/test_mkn_missing_service.json"],
        timeout=90,
    )
    if code == 0:
        print(
            "\nFAIL: missing service test exited 0; expected failure."
        )
        return False
    expected = (
        "imports missing service 'non_existent_svc' "
        "from online node 'basic_server'"
    )
    if expected not in output:
        print(
            f"\nFAIL: expected '{expected}' in output.\n"
            + output.strip()
        )
        return False
    return True


def build_integration_tests():
    """Build the list of mkn integration test (name, callable) pairs.

    Returns:
        list[tuple[str, callable]]: Integration test pairs.
    """
    return [
        ("mkn_basic_topology", test_mkn_basic_topology),
        ("mkn_namespace_split", test_mkn_namespace_split),
        ("mkn_client_timeout_slow", test_mkn_client_timeout_slow),
        ("mkn_client_timeout_exec", test_mkn_client_timeout_exec),
        ("mkn_missing_service", test_mkn_missing_service),
    ]


# ---------------------------------------------------------------------------
# Lock group integration suite (external runner)
# ---------------------------------------------------------------------------

LOCK_GROUP_RUNNER = (
    "scripts/tests/integration/lock_group/test_lock_groups.py"
)


def run_lock_group_suite():
    """Delegate to the lock group integration suite runner.

    Spawns run_lock_tests.py as a subprocess so its cargo-style output
    is streamed directly to stdout.

    Returns:
        bool: True if the suite passed.
    """
    result = subprocess.run(
        [sys.executable, LOCK_GROUP_RUNNER],
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run unit tests, then integration tests, then lock group suite."""
    total_passed = 0
    total_failed = 0

    # Phase 1: unit tests
    p, f = run_suite("unit tests", build_unit_tests())
    total_passed += p
    total_failed += f

    # Phase 2: mkn integration tests
    p, f = run_suite("integration tests", build_integration_tests())
    total_passed += p
    total_failed += f

    # Phase 3: lock group integration suite
    lock_ok = run_lock_group_suite()
    if not lock_ok:
        total_failed += 1

    # Final summary
    overall = "ok" if total_failed == 0 else "FAILED"
    print(
        f"overall test result: {overall}. "
        f"{total_passed} passed; {total_failed} failed."
    )
    sys.exit(0 if total_failed == 0 else 1)


main()
