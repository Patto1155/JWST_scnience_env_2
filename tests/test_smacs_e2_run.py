"""An interrupted reference remains reserved against the approved total cap."""

import subprocess
import sys

import pytest

from discovery.smacs_e2_run import CAP, PRIOR, child_rss_kib, reserve


def test_previous_conservative_charge_is_not_reset():
    ledger = {"reserved_total_bytes": PRIOR}
    reserve(ledger, 151_113_600)
    reserve(ledger, 4_732_087_416)
    assert ledger["reserved_total_bytes"] == 5_109_871_416


def test_dark_retry_would_exceed_the_remaining_allowance():
    ledger = {"reserved_total_bytes": 5_109_871_416}
    with pytest.raises(ValueError, match="cap"):
        reserve(ledger, 4_378_878_720)
    assert ledger["reserved_total_bytes"] == 5_109_871_416


def test_exact_cap_allowed_and_extra_byte_denied():
    ledger = {"reserved_total_bytes": CAP - 1}
    reserve(ledger, 1)
    with pytest.raises(ValueError):
        reserve(ledger, 1)


def test_actual_child_memory_is_resolved_across_procfs_namespaces():
    child = subprocess.Popen(
        [sys.executable, "-c", "x=bytearray(16*1024*1024); print('ready', flush=True); input()"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout.readline().strip() == "ready"
        rss = child_rss_kib(child.pid)
        assert rss is not None and rss >= 16 * 1024
    finally:
        child.communicate("\n", timeout=5)
