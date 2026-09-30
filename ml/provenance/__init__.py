"""Phase 6 — tamper-evident cryptographic provenance ledger.

SHA-256 hash-chained record store (Module 3 of docs/ml-methodology.md).
Append-only by convention; the only UPDATE path is the labeled
tamper-demo sandbox used to prove detection works.
"""

from ml.provenance.chain import (
    GENESIS_HASH,
    append_record,
    compute_record_hash,
    get_chain,
    reset_chain,
    tamper_demo,
    verify_chain,
)

__all__ = [
    "GENESIS_HASH",
    "append_record",
    "compute_record_hash",
    "get_chain",
    "reset_chain",
    "tamper_demo",
    "verify_chain",
]
