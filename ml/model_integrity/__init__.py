"""Module 2 — Model integrity (bounded prototype).

Registry + checks per docs/ml-methodology.md. Registration is
metadata-only by default: a .pkl is marked executable only when its
KavachAI signed manifest verifies (allowlist rule); .onnx/.pt/.pth are
parsed for metadata only and never executed. No external network, no
fabricated numbers — every check reports measured values.
"""
