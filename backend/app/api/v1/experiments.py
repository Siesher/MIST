"""Experiment API endpoints for A/B testing."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.database import get_db
from backend.app.services.experiment_service import get_experiment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/experiments", tags=["experiments"])


class CreateExperimentRequest(BaseModel):
    name: str
    description: str = ""
    control_mode: str = "chat"
    treatment_mode: str = "guided_learning"


class EnrollRequest(BaseModel):
    experiment_id: str
    user_id: str


class ScoreRequest(BaseModel):
    experiment_id: str
    user_id: str
    score: float


@router.post("")
async def create_experiment(req: CreateExperimentRequest, db: AsyncSession = Depends(get_db)):
    """Create a new A/B experiment."""
    service = await get_experiment_service()
    experiment = await service.create_experiment(
        db, req.name, req.description, req.control_mode, req.treatment_mode,
    )
    return {
        "experiment_id": experiment.id,
        "name": experiment.name,
        "control_mode": experiment.control_mode,
        "treatment_mode": experiment.treatment_mode,
    }


@router.post("/enroll")
async def enroll_participant(req: EnrollRequest, db: AsyncSession = Depends(get_db)):
    """Enroll a user in an experiment with random group assignment."""
    service = await get_experiment_service()
    participant = await service.enroll_participant(db, req.experiment_id, req.user_id)
    return {
        "participant_id": participant.id,
        "group": participant.group,
        "experiment_id": participant.experiment_id,
    }


@router.post("/pre-test")
async def record_pre_test(req: ScoreRequest, db: AsyncSession = Depends(get_db)):
    """Record pre-test score for a participant."""
    service = await get_experiment_service()
    ok = await service.record_pre_test(db, req.experiment_id, req.user_id, req.score)
    if not ok:
        raise HTTPException(status_code=404, detail="Participant not found")
    return {"status": "ok"}


@router.post("/post-test")
async def record_post_test(req: ScoreRequest, db: AsyncSession = Depends(get_db)):
    """Record post-test score for a participant."""
    service = await get_experiment_service()
    ok = await service.record_post_test(db, req.experiment_id, req.user_id, req.score)
    if not ok:
        raise HTTPException(status_code=404, detail="Participant not found")
    return {"status": "ok"}


@router.get("/{experiment_id}/results")
async def get_results(experiment_id: str, db: AsyncSession = Depends(get_db)):
    """Get experiment results with statistical analysis."""
    service = await get_experiment_service()
    results = await service.get_results(db, experiment_id)
    if not results:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Run statistical analysis if we have scores
    control_pre, control_post = [], []
    treatment_pre, treatment_post = [], []

    for p in results.get("control", {}).get("participants", []):
        if p["pre_test"] is not None and p["post_test"] is not None:
            control_pre.append(p["pre_test"])
            control_post.append(p["post_test"])

    for p in results.get("treatment", {}).get("participants", []):
        if p["pre_test"] is not None and p["post_test"] is not None:
            treatment_pre.append(p["pre_test"])
            treatment_post.append(p["post_test"])

    analysis = None
    if len(control_pre) >= 2 and len(treatment_pre) >= 2:
        from evaluation.experiment_analysis import analyze_experiment, format_report
        from dataclasses import asdict
        stats = analyze_experiment(control_pre, control_post, treatment_pre, treatment_post)
        analysis = {
            "t_statistic": stats.t_statistic,
            "p_value": stats.p_value,
            "cohens_d": stats.cohens_d,
            "ci_lower": stats.ci_lower,
            "ci_upper": stats.ci_upper,
            "significant": stats.significant,
            "report": format_report(stats),
        }

    results["analysis"] = analysis
    return results
