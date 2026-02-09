"""Experiment service for A/B testing framework."""

import random
import logging
from typing import Optional, Dict, Any, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.tables import ExperimentTable, ExperimentParticipantTable

logger = logging.getLogger(__name__)


class ExperimentService:
    """Service for managing A/B experiments."""

    async def create_experiment(
        self,
        db: AsyncSession,
        name: str,
        description: str = "",
        control_mode: str = "chat",
        treatment_mode: str = "guided_learning",
    ) -> ExperimentTable:
        """Create a new experiment."""
        experiment = ExperimentTable(
            name=name,
            description=description,
            control_mode=control_mode,
            treatment_mode=treatment_mode,
        )
        db.add(experiment)
        await db.commit()
        await db.refresh(experiment)
        logger.info(f"Created experiment: {experiment.id} ({name})")
        return experiment

    async def enroll_participant(
        self,
        db: AsyncSession,
        experiment_id: str,
        user_id: str,
    ) -> ExperimentParticipantTable:
        """Enroll a user in an experiment with random group assignment."""
        # Check if already enrolled
        result = await db.execute(
            select(ExperimentParticipantTable).where(
                ExperimentParticipantTable.experiment_id == experiment_id,
                ExperimentParticipantTable.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        # Count current groups for balance
        result = await db.execute(
            select(ExperimentParticipantTable).where(
                ExperimentParticipantTable.experiment_id == experiment_id,
            )
        )
        participants = result.scalars().all()
        control_count = sum(1 for p in participants if p.group == "control")
        treatment_count = sum(1 for p in participants if p.group == "treatment")

        # Assign to smaller group, or random if equal
        if control_count < treatment_count:
            group = "control"
        elif treatment_count < control_count:
            group = "treatment"
        else:
            group = random.choice(["control", "treatment"])

        participant = ExperimentParticipantTable(
            experiment_id=experiment_id,
            user_id=user_id,
            group=group,
        )
        db.add(participant)
        await db.commit()
        await db.refresh(participant)
        logger.info(f"Enrolled user {user_id} in experiment {experiment_id} as {group}")
        return participant

    async def record_pre_test(
        self,
        db: AsyncSession,
        experiment_id: str,
        user_id: str,
        score: float,
    ) -> bool:
        """Record pre-test score for a participant."""
        result = await db.execute(
            select(ExperimentParticipantTable).where(
                ExperimentParticipantTable.experiment_id == experiment_id,
                ExperimentParticipantTable.user_id == user_id,
            )
        )
        participant = result.scalar_one_or_none()
        if not participant:
            return False

        participant.pre_test_score = score
        await db.commit()
        return True

    async def record_post_test(
        self,
        db: AsyncSession,
        experiment_id: str,
        user_id: str,
        score: float,
    ) -> bool:
        """Record post-test score for a participant."""
        result = await db.execute(
            select(ExperimentParticipantTable).where(
                ExperimentParticipantTable.experiment_id == experiment_id,
                ExperimentParticipantTable.user_id == user_id,
            )
        )
        participant = result.scalar_one_or_none()
        if not participant:
            return False

        participant.post_test_score = score
        await db.commit()
        return True

    async def get_experiment(self, db: AsyncSession, experiment_id: str) -> Optional[ExperimentTable]:
        """Get experiment by ID."""
        result = await db.execute(
            select(ExperimentTable).where(ExperimentTable.id == experiment_id)
        )
        return result.scalar_one_or_none()

    async def get_results(self, db: AsyncSession, experiment_id: str) -> Dict[str, Any]:
        """Get experiment results with all participants."""
        experiment = await self.get_experiment(db, experiment_id)
        if not experiment:
            return {}

        result = await db.execute(
            select(ExperimentParticipantTable).where(
                ExperimentParticipantTable.experiment_id == experiment_id,
            )
        )
        participants = result.scalars().all()

        control = [p for p in participants if p.group == "control"]
        treatment = [p for p in participants if p.group == "treatment"]

        return {
            "experiment_id": experiment.id,
            "name": experiment.name,
            "control_mode": experiment.control_mode,
            "treatment_mode": experiment.treatment_mode,
            "status": experiment.status,
            "control": {
                "count": len(control),
                "participants": [
                    {
                        "user_id": p.user_id,
                        "pre_test": p.pre_test_score,
                        "post_test": p.post_test_score,
                    }
                    for p in control
                ],
            },
            "treatment": {
                "count": len(treatment),
                "participants": [
                    {
                        "user_id": p.user_id,
                        "pre_test": p.pre_test_score,
                        "post_test": p.post_test_score,
                    }
                    for p in treatment
                ],
            },
        }

    async def get_user_group(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> Optional[Dict[str, str]]:
        """Get the experiment group for a user (if enrolled in any active experiment)."""
        result = await db.execute(
            select(ExperimentParticipantTable, ExperimentTable)
            .join(ExperimentTable)
            .where(
                ExperimentParticipantTable.user_id == user_id,
                ExperimentTable.status == "active",
            )
        )
        row = result.first()
        if not row:
            return None

        participant, experiment = row
        mode = experiment.control_mode if participant.group == "control" else experiment.treatment_mode
        return {
            "experiment_id": experiment.id,
            "group": participant.group,
            "forced_mode": mode,
        }


_experiment_service: Optional[ExperimentService] = None


async def get_experiment_service() -> ExperimentService:
    global _experiment_service
    if _experiment_service is None:
        _experiment_service = ExperimentService()
    return _experiment_service
