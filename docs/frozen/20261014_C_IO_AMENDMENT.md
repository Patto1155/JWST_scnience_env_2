# C I/O-only amendment, 2026-10-14

Commit before next acquisition. Preserve 43a2b84 scientific freeze, sources,
noise controls, prior and statistic unchanged. Two interrupted header-scan
attempts remain charged to the same fresh counter; their receipts are retained.

To avoid thousands of 2880-byte remote header requests per CAL, request each
CAL in a single exact HTTP range covering its declared full length. Nine CALs
need approximately 464 MB. Retain in temporary BytesIO memory, close immediately
after source-array/metadata reduction; RATE remains stripe-range acquisition.
Four file-pair workers bound temporary full-CAL memory to about 207 MB plus
arrays/parser overhead. More than5 GB disk must remain free at launch.
The RangeBudget reserves expected bytes plus one before every response and
charges failures conservatively. The next CLI cap is remaining1,604,550,200
bytes; prior reservations6,062,536 plus that cap equals1,610,612,736.
Never commit raw full-CAL bodies. Existing code continues to label whole-file
hash unverified: an exact range is not a hash check. No new outcome was fitted
or inspected by the aborted attempts; they stopped during header acquisition.
