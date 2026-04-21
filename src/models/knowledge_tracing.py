"""
Knowledge Tracing — Отслеживание знаний студента

Реализует гибридный подход BKT + DKT:
- Bayesian Knowledge Tracing (BKT) для новых пользователей
- Deep Knowledge Tracing (DKT) для пользователей с достаточной историей

На основе исследований:
- Deep Knowledge Tracing (Piech et al., 2015)
- RL-DKT (2025) - улучшение на 12.5% в completion rate
- Ebbinghaus Forgetting Curve для моделирования забывания
"""

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import math
import logging

if TYPE_CHECKING:
    from src.models.dkt_model import DKTModel

logger = logging.getLogger(__name__)


@dataclass
class SkillState:
    """Состояние одного навыка."""
    name: str
    mastery: float = 0.3  # P(L) - вероятность владения
    attempts: int = 0
    successes: int = 0
    last_practice: Optional[datetime] = None

    # BKT параметры (можно настраивать под навык)
    p_init: float = 0.3    # Начальная вероятность владения
    p_learn: float = 0.1   # Вероятность выучить за одну попытку
    p_forget: float = 0.05 # Вероятность забыть
    p_guess: float = 0.2   # Вероятность угадать
    p_slip: float = 0.1    # Вероятность ошибиться зная

    # DKT tracking
    dkt_mastery: Optional[float] = None  # Mastery from DKT model
    use_dkt: bool = False  # Whether to use DKT for this skill


# Knowledge decay parameters based on Ebbinghaus forgetting curve
# R = e^(-t/S) where t is time and S is memory strength
DECAY_BASE_HALF_LIFE_HOURS = 24 * 7  # 1 week half-life for weak memory
DECAY_MASTERED_HALF_LIFE_HOURS = 24 * 30  # 1 month for mastered skills
DECAY_MINIMUM_MASTERY = 0.1  # Don't decay below this


def calculate_decay_factor(
    hours_since_practice: float,
    mastery_level: float,
    practice_count: int = 1
) -> float:
    """
    Calculate decay factor using Ebbinghaus forgetting curve.

    The formula: R = e^(-t/S)
    where:
    - R is retention
    - t is time since last practice
    - S is memory strength (depends on mastery and practice count)

    Args:
        hours_since_practice: Hours since last practice
        mastery_level: Current mastery level (0-1)
        practice_count: Number of times practiced (strengthens memory)

    Returns:
        Decay factor (0-1) to multiply with current mastery
    """
    if hours_since_practice <= 0:
        return 1.0

    # Memory strength increases with mastery and practice
    # Higher mastery = slower decay
    base_strength = DECAY_BASE_HALF_LIFE_HOURS

    # Mastery bonus: up to 3x strength at mastery=1.0
    mastery_multiplier = 1.0 + (mastery_level * 2.0)

    # Practice bonus: each practice increases strength by 20% (diminishing)
    practice_multiplier = 1.0 + (math.log1p(practice_count) * 0.2)

    memory_strength = base_strength * mastery_multiplier * practice_multiplier

    # Ebbinghaus formula
    decay = math.exp(-hours_since_practice / memory_strength)

    return max(decay, DECAY_MINIMUM_MASTERY / mastery_level if mastery_level > 0 else 1.0)


@dataclass
class StudentModel:
    """
    Модель знаний студента с гибридным BKT/DKT подходом.

    - Использует BKT для новых пользователей (< DKT_THRESHOLD взаимодействий)
    - Переключается на DKT после накопления достаточной истории
    - Применяет Ebbinghaus forgetting curve для моделирования забывания
    """
    student_id: str
    skills: Dict[str, SkillState] = field(default_factory=dict)
    total_sessions: int = 0
    total_problems_solved: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    # Interaction history for DKT
    interaction_history: List[Tuple[int, bool]] = field(default_factory=list)

    # DKT settings
    dkt_threshold: int = 10  # Switch to DKT after this many interactions
    dkt_model: Optional["DKTModel"] = field(default=None, repr=False)
    use_dkt_globally: bool = False  # Whether DKT is active

    # Skill name to ID mapping for DKT
    skill_to_id: Dict[str, int] = field(default_factory=dict)
    id_to_skill: Dict[int, str] = field(default_factory=dict)
    next_skill_id: int = 0
    
    # Иерархия навыков (skill -> prerequisites)
    SKILL_HIERARCHY = {
        # Базовая алгебра
        "arithmetic": [],
        "fractions": ["arithmetic"],
        "linear_equations": ["arithmetic"],
        "quadratic_equations": ["linear_equations"],
        
        # Функции
        "functions_basics": ["linear_equations"],
        "function_composition": ["functions_basics"],
        
        # Calculus
        "limits": ["functions_basics"],
        "derivatives_basic": ["limits"],
        "power_rule": ["derivatives_basic"],
        "product_rule": ["derivatives_basic"],
        "quotient_rule": ["derivatives_basic"],
        "chain_rule": ["derivatives_basic", "function_composition"],
        "derivatives_advanced": ["power_rule", "product_rule", "chain_rule"],
        
        "integrals_basic": ["derivatives_basic"],
        "integration_by_parts": ["integrals_basic", "product_rule"],
        "integration_substitution": ["integrals_basic", "chain_rule"],
        
        # Тригонометрия
        "trigonometry_basics": ["functions_basics"],
        "trig_identities": ["trigonometry_basics"],
        "trig_derivatives": ["derivatives_basic", "trigonometry_basics"],
        
        # Программирование
        "variables": [],
        "conditionals": ["variables"],
        "loops": ["conditionals"],
        "functions_prog": ["loops"],
        "recursion": ["functions_prog"],
        "data_structures": ["loops"],
        "algorithms": ["data_structures", "recursion"],
        "oop": ["functions_prog"],
    }
    
    def get_skill(self, skill_name: str) -> SkillState:
        """Получить или создать состояние навыка."""
        if skill_name not in self.skills:
            self.skills[skill_name] = SkillState(name=skill_name)
            # Assign skill ID for DKT
            if skill_name not in self.skill_to_id:
                self.skill_to_id[skill_name] = self.next_skill_id
                self.id_to_skill[self.next_skill_id] = skill_name
                self.next_skill_id += 1
        return self.skills[skill_name]

    def _get_skill_id(self, skill_name: str) -> int:
        """Get or create skill ID for DKT model."""
        if skill_name not in self.skill_to_id:
            self.skill_to_id[skill_name] = self.next_skill_id
            self.id_to_skill[self.next_skill_id] = skill_name
            self.next_skill_id += 1
        return self.skill_to_id[skill_name]

    def _check_dkt_transition(self) -> bool:
        """
        Check if we should transition from BKT to DKT.

        Returns True if:
        - We have enough interactions (>= dkt_threshold)
        - DKT model is available
        """
        if self.use_dkt_globally:
            return True

        if len(self.interaction_history) >= self.dkt_threshold:
            if self.dkt_model is not None:
                self.use_dkt_globally = True
                logger.info(
                    f"Student {self.student_id}: Transitioning to DKT "
                    f"after {len(self.interaction_history)} interactions"
                )
                return True
            else:
                logger.debug(
                    f"Student {self.student_id}: Would transition to DKT but model not available"
                )
        return False

    def set_dkt_model(self, model: "DKTModel"):
        """Set the DKT model for this student."""
        self.dkt_model = model
        # Check if we should enable DKT
        self._check_dkt_transition()

    def _update_dkt_predictions(self):
        """Update mastery predictions using DKT model."""
        if not self.dkt_model or not self.interaction_history:
            return

        try:
            predictions = self.dkt_model.predict_next(self.interaction_history)

            # Update DKT mastery for known skills
            for skill_id, prob in predictions.items():
                if skill_id in self.id_to_skill:
                    skill_name = self.id_to_skill[skill_id]
                    if skill_name in self.skills:
                        self.skills[skill_name].dkt_mastery = prob
                        self.skills[skill_name].use_dkt = True

            logger.debug(f"Updated DKT predictions for {len(predictions)} skills")
        except Exception as e:
            logger.warning(f"DKT prediction failed: {e}")

    def apply_knowledge_decay(self, current_time: Optional[datetime] = None):
        """
        Apply Ebbinghaus forgetting curve to all skills.

        Should be called at the start of each session to model
        knowledge decay since last practice.

        Args:
            current_time: Current time (defaults to now)
        """
        if current_time is None:
            current_time = datetime.now()

        decayed_skills = []

        for skill_name, skill in self.skills.items():
            if skill.last_practice is None:
                continue

            # Calculate time since last practice
            time_delta = current_time - skill.last_practice
            hours_since = time_delta.total_seconds() / 3600

            if hours_since < 1:  # Less than 1 hour, no decay
                continue

            # Calculate decay factor
            old_mastery = skill.mastery
            decay_factor = calculate_decay_factor(
                hours_since_practice=hours_since,
                mastery_level=skill.mastery,
                practice_count=skill.attempts
            )

            # Apply decay
            new_mastery = skill.mastery * decay_factor
            new_mastery = max(DECAY_MINIMUM_MASTERY, new_mastery)

            if abs(new_mastery - old_mastery) > 0.01:
                skill.mastery = new_mastery
                decayed_skills.append((skill_name, old_mastery, new_mastery))

        if decayed_skills:
            logger.info(
                f"Applied knowledge decay to {len(decayed_skills)} skills "
                f"for student {self.student_id}"
            )
            for name, old, new in decayed_skills[:3]:
                logger.debug(f"  {name}: {old:.2f} -> {new:.2f}")

        return decayed_skills
    
    def update_skill(self, skill_name: str, is_correct: bool) -> float:
        """
        Обновить mastery навыка используя гибридный BKT/DKT подход.

        - Для новых пользователей: используем BKT
        - После DKT_THRESHOLD взаимодействий: переключаемся на DKT

        Формула BKT:
        P(L_n | obs) = P(L_n-1) * P(obs | L) / P(obs)

        Возвращает новый уровень mastery.
        """
        skill = self.get_skill(skill_name)
        skill.attempts += 1
        skill.last_practice = datetime.now()

        if is_correct:
            skill.successes += 1

        # Record interaction for DKT
        skill_id = self._get_skill_id(skill_name)
        self.interaction_history.append((skill_id, is_correct))

        # Check if we should transition to DKT
        use_dkt = self._check_dkt_transition()

        if use_dkt and self.dkt_model is not None:
            # Use DKT for prediction
            self._update_dkt_predictions()

            # If DKT gave us a prediction, use weighted combination
            if skill.dkt_mastery is not None:
                # BKT update (still useful for immediate feedback)
                bkt_mastery = self._bkt_update(skill, is_correct)

                # Weighted combination: prefer DKT as history grows
                dkt_weight = min(0.8, len(self.interaction_history) / 50)
                bkt_weight = 1.0 - dkt_weight

                skill.mastery = bkt_weight * bkt_mastery + dkt_weight * skill.dkt_mastery
                skill.mastery = min(0.99, max(0.01, skill.mastery))

                logger.debug(
                    f"Hybrid update for {skill_name}: "
                    f"BKT={bkt_mastery:.2f}, DKT={skill.dkt_mastery:.2f}, "
                    f"Combined={skill.mastery:.2f}"
                )
                return skill.mastery

        # Fallback to pure BKT
        skill.mastery = self._bkt_update(skill, is_correct)
        return skill.mastery

    def _bkt_update(self, skill: SkillState, is_correct: bool) -> float:
        """
        Pure BKT update calculation.

        Args:
            skill: The skill state to update
            is_correct: Whether the response was correct

        Returns:
            Updated mastery value
        """
        p_l = skill.mastery  # Prior P(L)

        if is_correct:
            # P(correct | L) = 1 - p_slip
            # P(correct | ~L) = p_guess
            p_obs_given_l = 1 - skill.p_slip
            p_obs_given_not_l = skill.p_guess
        else:
            # P(incorrect | L) = p_slip
            # P(incorrect | ~L) = 1 - p_guess
            p_obs_given_l = skill.p_slip
            p_obs_given_not_l = 1 - skill.p_guess

        # Bayes update
        p_obs = p_l * p_obs_given_l + (1 - p_l) * p_obs_given_not_l
        p_l_posterior = (p_l * p_obs_given_l) / p_obs if p_obs > 0 else p_l

        # Learning update: даже если не знал, мог выучить
        p_l_new = p_l_posterior + (1 - p_l_posterior) * skill.p_learn

        return min(0.99, max(0.01, p_l_new))
    
    def get_mastery(self, skill_name: str) -> float:
        """Получить текущий уровень владения навыком."""
        return self.get_skill(skill_name).mastery
    
    def get_weakest_skills(self, n: int = 3) -> List[Tuple[str, float]]:
        """Получить N самых слабых навыков."""
        if not self.skills:
            return []
        
        sorted_skills = sorted(
            self.skills.items(),
            key=lambda x: x[1].mastery
        )
        return [(s.name, s.mastery) for _, s in sorted_skills[:n]]
    
    def get_strongest_skills(self, n: int = 3) -> List[Tuple[str, float]]:
        """Получить N самых сильных навыков."""
        if not self.skills:
            return []
        
        sorted_skills = sorted(
            self.skills.items(),
            key=lambda x: x[1].mastery,
            reverse=True
        )
        return [(s.name, s.mastery) for _, s in sorted_skills[:n]]
    
    def get_ready_skills(self) -> List[str]:
        """
        Получить навыки, к изучению которых студент готов
        (все prerequisites освоены на >0.6).
        """
        ready = []
        for skill, prereqs in self.SKILL_HIERARCHY.items():
            if skill in self.skills and self.skills[skill].mastery > 0.6:
                continue  # Уже освоен
            
            # Проверяем prerequisites
            prereqs_met = all(
                self.get_mastery(p) > 0.6 for p in prereqs
            ) if prereqs else True
            
            if prereqs_met:
                ready.append(skill)
        
        return ready
    
    def recommend_next_skill(self) -> Optional[str]:
        """Рекомендовать следующий навык для изучения."""
        ready = self.get_ready_skills()
        if not ready:
            return None
        
        # Выбираем навык с наименьшим mastery из готовых
        return min(ready, key=lambda s: self.get_mastery(s))
    
    def predict_success(self, skill_name: str) -> float:
        """
        Предсказать вероятность успеха на задаче с данным навыком.
        
        P(correct) = P(L) * (1 - p_slip) + (1 - P(L)) * p_guess
        """
        skill = self.get_skill(skill_name)
        p_l = skill.mastery
        
        return p_l * (1 - skill.p_slip) + (1 - p_l) * skill.p_guess
    
    def get_recommended_difficulty(self) -> str:
        """Рекомендовать сложность следующей задачи."""
        if not self.skills:
            return "easy"
        
        avg_mastery = sum(s.mastery for s in self.skills.values()) / len(self.skills)
        
        if avg_mastery < 0.3:
            return "easy"
        elif avg_mastery < 0.5:
            return "medium"
        elif avg_mastery < 0.7:
            return "hard"
        else:
            return "olympiad"
    
    def to_dict(self) -> dict:
        """Сериализация в словарь."""
        return {
            "student_id": self.student_id,
            "skills": {
                name: {
                    "mastery": skill.mastery,
                    "attempts": skill.attempts,
                    "successes": skill.successes,
                    "last_practice": skill.last_practice.isoformat() if skill.last_practice else None,
                    "dkt_mastery": skill.dkt_mastery,
                    "use_dkt": skill.use_dkt
                }
                for name, skill in self.skills.items()
            },
            "total_sessions": self.total_sessions,
            "total_problems_solved": self.total_problems_solved,
            "created_at": self.created_at.isoformat(),
            # DKT state
            "interaction_history": self.interaction_history,
            "use_dkt_globally": self.use_dkt_globally,
            "skill_to_id": self.skill_to_id,
            "next_skill_id": self.next_skill_id
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "StudentModel":
        """Десериализация из словаря."""
        model = cls(student_id=data["student_id"])
        model.total_sessions = data.get("total_sessions", 0)
        model.total_problems_solved = data.get("total_problems_solved", 0)

        for name, skill_data in data.get("skills", {}).items():
            skill = SkillState(name=name)
            skill.mastery = skill_data.get("mastery", 0.3)
            skill.attempts = skill_data.get("attempts", 0)
            skill.successes = skill_data.get("successes", 0)
            if skill_data.get("last_practice"):
                skill.last_practice = datetime.fromisoformat(skill_data["last_practice"])
            skill.dkt_mastery = skill_data.get("dkt_mastery")
            skill.use_dkt = skill_data.get("use_dkt", False)
            model.skills[name] = skill

        # Restore DKT state
        model.interaction_history = [
            tuple(x) for x in data.get("interaction_history", [])
        ]
        model.use_dkt_globally = data.get("use_dkt_globally", False)
        model.skill_to_id = data.get("skill_to_id", {})
        model.id_to_skill = {int(v): k for k, v in model.skill_to_id.items()}
        model.next_skill_id = data.get("next_skill_id", len(model.skill_to_id))

        return model
    
    def get_summary(self) -> str:
        """Получить текстовое резюме знаний студента."""
        if not self.skills:
            return "📊 Пока нет данных о навыках"
        
        lines = ["📊 **Профиль знаний:**\n"]
        
        # Сильные навыки
        strong = self.get_strongest_skills(3)
        if strong:
            lines.append("💪 **Сильные стороны:**")
            for skill, mastery in strong:
                bar = "█" * int(mastery * 10) + "░" * (10 - int(mastery * 10))
                lines.append(f"  • {skill}: {bar} {mastery:.0%}")
        
        # Слабые навыки
        weak = self.get_weakest_skills(3)
        if weak:
            lines.append("\n📈 **Нужно подтянуть:**")
            for skill, mastery in weak:
                bar = "█" * int(mastery * 10) + "░" * (10 - int(mastery * 10))
                lines.append(f"  • {skill}: {bar} {mastery:.0%}")
        
        # Рекомендация
        next_skill = self.recommend_next_skill()
        if next_skill:
            lines.append(f"\n🎯 **Рекомендую изучить:** {next_skill}")
        
        lines.append(f"\n📚 Решено задач: {self.total_problems_solved}")
        
        return "\n".join(lines)


class KnowledgeTracker:
    """
    Менеджер для отслеживания знаний множества студентов.

    Поддерживает:
    - Гибридный BKT/DKT подход
    - Автоматический переход на DKT после достаточного количества взаимодействий
    - Моделирование забывания (Ebbinghaus curve)
    """

    def __init__(
        self,
        storage_path: str = "./data/students",
        dkt_model: Optional["DKTModel"] = None,
        dkt_threshold: int = 10,
        enable_decay: bool = True,
        dkt_weights_path: str = "data/models/dkt_pretrained.pt",
    ):
        """
        Initialize KnowledgeTracker.

        Args:
            storage_path: Path to store student profiles
            dkt_model: Optional DKT model for enhanced tracking
            dkt_threshold: Interactions before switching to DKT
            enable_decay: Whether to apply knowledge decay
            dkt_weights_path: Path to pre-trained DKT weights (auto-loaded if exists)
        """
        self.storage_path = storage_path
        self.students: Dict[str, StudentModel] = {}
        self.dkt_model = dkt_model
        self.dkt_threshold = dkt_threshold
        self.enable_decay = enable_decay

        # Auto-load pre-trained DKT weights if available and no model provided
        if self.dkt_model is None:
            try:
                from src.models.dkt_model import DKTModel
                loaded = DKTModel.from_pretrained(dkt_weights_path)
                if loaded is not None:
                    self.dkt_model = loaded
                    logger.info(f"Auto-loaded pre-trained DKT from {dkt_weights_path}")
            except Exception as e:
                logger.debug(f"DKT auto-load skipped: {e}")

        # Создаём директорию если нет
        import os
        os.makedirs(storage_path, exist_ok=True)

        logger.info(
            f"KnowledgeTracker initialized: "
            f"DKT={'enabled' if self.dkt_model else 'disabled'}, "
            f"threshold={dkt_threshold}, decay={enable_decay}"
        )

    def set_dkt_model(self, model: "DKTModel"):
        """
        Set or update the DKT model.

        This will also update all loaded students.
        """
        self.dkt_model = model
        for student in self.students.values():
            student.set_dkt_model(model)
        logger.info("DKT model set for KnowledgeTracker")

    def get_student(self, student_id: str, apply_decay: bool = True) -> StudentModel:
        """
        Получить или создать модель студента.

        Args:
            student_id: Student identifier
            apply_decay: Whether to apply knowledge decay (default True)

        Returns:
            StudentModel instance
        """
        if student_id not in self.students:
            # Пробуем загрузить с диска
            filepath = f"{self.storage_path}/{student_id}.json"
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    student = StudentModel.from_dict(data)
                    student.dkt_threshold = self.dkt_threshold
                    if self.dkt_model:
                        student.set_dkt_model(self.dkt_model)
                    self.students[student_id] = student
            except FileNotFoundError:
                student = StudentModel(
                    student_id=student_id,
                    dkt_threshold=self.dkt_threshold
                )
                if self.dkt_model:
                    student.set_dkt_model(self.dkt_model)
                self.students[student_id] = student

        student = self.students[student_id]

        # Apply knowledge decay if enabled
        if apply_decay and self.enable_decay:
            student.apply_knowledge_decay()

        return student

    def save_student(self, student_id: str):
        """Сохранить модель студента на диск."""
        if student_id in self.students:
            filepath = f"{self.storage_path}/{student_id}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.students[student_id].to_dict(), f, ensure_ascii=False, indent=2)

    def record_attempt(
        self,
        student_id: str,
        skills: List[str],
        is_correct: bool
    ) -> Dict[str, float]:
        """
        Записать попытку решения задачи.

        Возвращает обновлённые уровни mastery для всех навыков.
        """
        student = self.get_student(student_id, apply_decay=False)

        updated = {}
        for skill in skills:
            new_mastery = student.update_skill(skill, is_correct)
            updated[skill] = new_mastery

        if is_correct:
            student.total_problems_solved += 1

        # Автосохранение
        self.save_student(student_id)

        return updated

    def start_session(self, student_id: str) -> StudentModel:
        """
        Start a new session for a student.

        This applies knowledge decay and increments session count.

        Args:
            student_id: Student identifier

        Returns:
            StudentModel with decay applied
        """
        student = self.get_student(student_id, apply_decay=True)
        student.total_sessions += 1
        self.save_student(student_id)

        logger.info(
            f"Session started for {student_id}: "
            f"session #{student.total_sessions}, "
            f"DKT={'active' if student.use_dkt_globally else 'inactive'}"
        )

        return student

    def get_knowledge_state_summary(self, student_id: str) -> Dict:
        """
        Get a summary of student's knowledge state.

        Returns:
            Dictionary with mastery levels and recommendations
        """
        student = self.get_student(student_id, apply_decay=False)

        return {
            "student_id": student_id,
            "total_interactions": len(student.interaction_history),
            "using_dkt": student.use_dkt_globally,
            "mastery_by_skill": {
                name: {
                    "mastery": skill.mastery,
                    "dkt_mastery": skill.dkt_mastery,
                    "attempts": skill.attempts,
                    "success_rate": skill.successes / skill.attempts if skill.attempts > 0 else 0
                }
                for name, skill in student.skills.items()
            },
            "weakest_skills": student.get_weakest_skills(3),
            "strongest_skills": student.get_strongest_skills(3),
            "recommended_skill": student.recommend_next_skill(),
            "recommended_difficulty": student.get_recommended_difficulty()
        }
