"""Integration test runner for MKN lock group cascade tests.

Runs the MKN (Meerkat Network Orchestrator) lock group integration
test suite and reports results in cargo-style test output format.

Location: scripts/tests/integration/lock_group/test_lock_groups.py
Run from workspace root: python3 scripts/tests/integration/lock_group/test_lock_groups.py
"""

import sys
import subprocess
import time

MANIFESTS = [
    (
        "cascade_lock_success",
        "scripts/tests/integration/lock_group/success.json",
    ),
    (
        "cascade_lock_abort_wait_die",
        "scripts/tests/integration/lock_group/abort.json",
    ),
    (
        "cascade_lock_wait_wake",
        "scripts/tests/integration/lock_group/wait.json",
    ),
]


def run_mkn(name, manifest):
    """Run a single MKN test manifest.

    Args:
        name (str): Short name of the test case.
        manifest (str): Path to the JSON manifest file.

    Returns:
        bool: True if the test passed, False otherwise.
    """
    print(f"test {name} ... ", end="", flush=True)
    res = subprocess.run(
        [sys.executable, "scripts/mkn.py", manifest],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print("FAILED")
        if res.stdout is not None and len(res.stdout) > 0:
            print(res.stdout, end="")
        if res.stderr is not None and len(res.stderr) > 0:
            print(res.stderr, end="")
        return False
    print("ok")
    return True


def main():
    """Run all MKN lock group tests and report cargo-style results."""
    runner = (
        "scripts/tests/integration/lock_group/test_lock_groups.py"
    )
    print(f"     Running {runner} (mkn lock group integration tests)")
    print()
    print(f"running {len(MANIFESTS)} tests")

    passed = 0
    failed = 0
    start = time.monotonic()

    for name, manifest in MANIFESTS:
        if run_mkn(name, manifest):
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

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
