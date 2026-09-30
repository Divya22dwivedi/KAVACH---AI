"""Pydantic request/response schemas for the KavachAI API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "low", "medium", "high", "critical"]
Disposition = Literal["ACCEPT", "REVIEW", "QUARANTINE"]
Category = Literal["data", "model", "provenance", "shift"]


class Health(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    db_ok: bool = True
    offline: bool = True


class Finding(BaseModel):
    id: str
    scan_id: str | None = None
    category: Category
    asset_id: str
    title: str
    detection_method: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity
    disposition: Disposition
    supported_attack_class: str | None = None
    limitations: str
    reviewer_note: str = ""
    created_at: str


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_format: Literal["folder", "csv", "yolo", "coco"]


class ScanRequest(BaseModel):
    dataset_id: str
    experiment_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ModelCheckRequest(BaseModel):
    reference_model_id: str | None = None
    probe_dataset_id: str | None = None


class PredictRequest(BaseModel):
    model_id: str
    sample_id: str | None = None
    image_base64: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ShiftRequest(BaseModel):
    reference_dataset_id: str
    current_dataset_id: str


class AttackGenerateRequest(BaseModel):
    scenario: Literal["clean", "label_flip", "trigger_patch",
                      "near_duplicate", "ood", "full_suite"]
    seed: int = 42
    n: int = Field(default=600, ge=10, le=5000)


class ReviewPatch(BaseModel):
    disposition: Disposition | None = None
    reviewer_note: str | None = Field(default=None, max_length=2000)


class ReportRequest(BaseModel):
    experiment_id: str


class DemoRequest(BaseModel):
    seed: int = 42
