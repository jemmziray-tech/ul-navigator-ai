"""Indicative QCA calculation using the official UL 2026/27 handbook."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

import json
from pathlib import Path

_RULES = json.loads((Path(__file__).resolve().parents[1] / "data/qca-rules.json").read_text(encoding="utf-8"))
QPV = {g["grade"]: g["qpv"] for g in _RULES["grades"]}
CLASSIFICATIONS = [(c["min_qca"], c["label"]) for c in _RULES["classifications"]]
SOURCES = _RULES["sources"]


class ModuleGrade(BaseModel):
    code: str = Field(default="", max_length=20)
    credits: float = Field(gt=0, le=60)
    grade: str
    semester: str = Field(default="", max_length=40)
    include: bool = True

    @field_validator("grade")
    @classmethod
    def _grade(cls, v: str) -> str:
        g = v.strip().upper()
        if g not in QPV:
            raise ValueError(f"Unknown UL grade '{v}'")
        return g


class QCARequest(BaseModel):
    modules: list[ModuleGrade] = Field(min_length=1, max_length=200)


def classify(qca: float) -> str | None:
    for threshold, label in CLASSIFICATIONS:
        if qca + 1e-9 >= threshold:
            return label
    return None


def calculate(req: QCARequest) -> dict:
    total_qp = total_cr = 0.0
    excluded: list[str] = []
    by_sem: dict[str, list[float]] = {}
    for m in req.modules:
        if not m.include:
            excluded.append(m.code or m.grade)
            continue
        qp = QPV[m.grade] * m.credits
        total_qp += qp
        total_cr += m.credits
        sem = by_sem.setdefault(m.semester or "All", [0.0, 0.0])
        sem[0] += qp
        sem[1] += m.credits
    raw_qca = total_qp / total_cr if total_cr else None
    qca = round(raw_qca, 2) if raw_qca is not None else None
    return {
        "qca": qca,
        "unrounded_qca": raw_qca,
        "academic_year": _RULES["academic_year"],
        "quality_points": round(total_qp, 2),
        "credits": total_cr,
        "classification": classify(raw_qca) if raw_qca is not None else None,
        "semesters": [{"semester": k, "qca": round(v[0] / v[1], 2) if v[1] else None,
                       "credits": v[1]} for k, v in by_sem.items()],
        "excluded_modules": excluded,
        "disclaimer": ("Indicative only. Award classification uses the cumulative QCA of the "
                       "relevant semesters as defined in the Handbook of Academic Regulations "
                       "and Procedures; discretionary bands and programme-specific rules may "
                       "apply. Always confirm with the Academic Registry."),
        "sources": SOURCES,
    }


def rules() -> dict:
    return _RULES
