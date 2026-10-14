import io

import pytest

from tools.jwst.ranged_fits import RangeBudget, RangedFITS


def test_cached_blocks_read_seek_and_cleanup_without_network(monkeypatch):
    stream = RangedFITS("https://example.invalid/test.fits", 12, RangeBudget(), block=4)
    stream.cache = {0: b"abcd", 4: b"efgh", 8: b"ijkl"}
    monkeypatch.setattr(stream.session, "get", lambda *a, **k: pytest.fail("network unexpected"))
    assert stream.read(6) == b"abcdef"
    stream.seek(-4, io.SEEK_END)
    assert stream.read() == b"ijkl"
    stream.seek(2)
    assert stream.read(4) == b"cdef"
    stream.close()
    assert not stream.cache


def test_budget_blocks_request_before_network(monkeypatch):
    stream = RangedFITS("https://example.invalid/test.fits", 12, RangeBudget(cap=3), block=4)
    monkeypatch.setattr(stream.session, "get", lambda *a, **k: pytest.fail("network unexpected"))
    with pytest.raises(ValueError, match="exceed"):
        stream.read(1)
    stream.close()


def test_astropy_section_uses_seekable_stream_and_preserves_values(monkeypatch):
    import numpy as np
    from astropy.io import fits

    values = np.arange(40 * 50, dtype=np.float32).reshape(40, 50)
    buffer = io.BytesIO()
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(values, name="SCI")]).writeto(buffer)
    raw = buffer.getvalue()
    stream = RangedFITS("https://example.invalid/test.fits", len(raw), RangeBudget(), block=2880)
    requested = []

    def block(start):
        requested.append(start)
        return raw[start : start + 2880]

    monkeypatch.setattr(stream, "_block", block)
    with fits.open(stream, memmap=False) as hdul:
        selected = hdul["SCI"].section[12:15, 9:18]
        assert np.array_equal(selected, values[12:15, 9:18])
    assert requested
    stream.close()


def test_wrong_range_is_rejected_and_charged(monkeypatch):
    class Response:
        status_code = 206
        headers = {"Content-Range": "bytes 4-7/12"}
        raw = io.BytesIO(b"abcd")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    stream = RangedFITS("https://example.invalid/test.fits", 12, RangeBudget(), block=4)
    monkeypatch.setattr(stream.session, "get", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="exact requested"):
        stream.read(1)
    assert stream.budget.bytes == 5
    assert stream.budget.receipts[0]["body_bytes"] == 4
    assert not stream.budget.receipts[0]["fullfile_hash_verified"]
    stream.close()


def test_header_mode_requests_exact_header_block(monkeypatch):
    from tools.jwst.ranged_fits import HeaderRangedFITS

    stream = HeaderRangedFITS("https://example.invalid/test.fits", 150000, RangeBudget())
    requests = []

    def fetch(start, count):
        requests.append((start, count))
        return b"x" * count

    monkeypatch.setattr(stream, "_fetch", fetch)
    stream.seek(72000)
    assert len(stream.read(2880)) == 2880
    assert requests == [(72000, 2880)]
    assert len(stream.read(47376)) == 47376
    assert requests[-1] == (74880, 47376)
    stream.close()


def test_parallel_budget_reservation_and_journal_survive_failure(tmp_path):
    import json

    budget = RangeBudget(cap=10, journal=tmp_path / "ranges.jsonl")
    attempt = {"utc": "frozen-test", "body_bytes": 0}
    budget.reserve(6, attempt)
    with pytest.raises(ValueError, match="exceed"):
        budget.reserve(5, {"utc": "second"})
    budget.finish(6, attempt, b"abc", KeyboardInterrupt("stop"))
    events = [json.loads(line) for line in budget.journal.read_text().splitlines()]
    assert [x["event"] for x in events] == [
        "request_started",
        "acquisition_stopped",
        "request_finished",
    ]
    assert events[-1]["body_bytes"] == 3
    assert events[-1]["charged_body_bytes"] == budget.bytes == 6
    assert not events[-1]["complete_body_accounting"]
    assert budget.reserved == 0
    assert "KeyboardInterrupt" in events[-1]["error"]


def test_cancelled_budget_cannot_start_new_transfer():
    budget = RangeBudget()
    budget.cancel_event.set()
    with pytest.raises(InterruptedError, match="no scientific null"):
        budget.reserve(4, {"utc": "stop-test"})
    assert not budget.receipts
    assert budget.bytes == 0


def test_offset_hint_matches_extension_identity_without_science_selection(monkeypatch):
    import numpy as np
    from astropy.io import fits

    from tools.jwst.ranged_fits import locate_hdu_header

    header = fits.Header({"EXTVER": 21, "SRCNAME": "5224_277193"})
    buffer = io.BytesIO()
    fits.HDUList(
        [fits.PrimaryHDU(), fits.ImageHDU(np.zeros((28, 423)), header=header, name="SCI")]
    ).writeto(buffer)
    raw = buffer.getvalue()
    stream = RangedFITS("https://example.invalid/test.fits", len(raw), RangeBudget())
    monkeypatch.setattr(stream, "_fetch", lambda start, count: raw[start : start + count])
    found, header_offset, data_offset = locate_hdu_header(stream, 2880, "SCI", 21)
    assert found["SRCNAME"] == "5224_277193"
    assert (header_offset, data_offset) == (2880, 5760)
    with pytest.raises(ValueError, match="declared extension"):
        locate_hdu_header(stream, 2880, "SCI", 22)
    stream.close()
