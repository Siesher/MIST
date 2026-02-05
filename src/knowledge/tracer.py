"""
Knowledge Tracing Module - Байесовское отслеживание знаний

Реализует BKT (Bayesian Knowledge Tracing) для оценки уровня знаний студента
по каждому навыку на основе истории ответов.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
import math


@dataclass
class SkillState:
    """Состояние знания одного навыка."""
    name: str
    mastery: float = 0.3  # P(L) - вероятность знания
    attempts: int = 0
    successes: int = 0
    last_attempt: Optional[datetime] = None
    history: List[bool] = field(default_factory=list)  # True = correct
    
    def success_rate(self) -> float:
        """Процент правильных ответов."""
        if self.attempts == 0:
            return 0.0
        return self.successes / self.attempts


@dataclass 
class BKTParams:
    """Параметры модели BKT для навыка."""
    p_init: float = 0.3    # P(L0) - начальное знание
    p_learn: float = 0.1   # P(T) - вероятность выучить за попытку
    p_forget: float = 0.05 # P(F) - вероятность забыть
    p_guess: float = 0.25  # P(G) - угадать без знания
    p_slip: float = 0.1    # P(S) - ошибиться при знании


class KnowledgeTracer:
    """
    Система отслеживания знаний студента.
    
    Использует Bayesian Knowledge Tracing (BKT) для оценки
    вероятности того, что студент освоил каждый навык.
    """
    
    # Иерархия навыков
    SKILL_TAXONOMY = {
        "algebra": {
            "name": "Алгебра",
            "subskills": [
                "linear_equations",
                "quadratic_equations", 
                "systems_of_equations",
                "inequalities",
                "polynomials",
                "factoring",
            ]
        },
        "calculus": {
            "name": "Мат. анализ",
            "subskills": [
                "limits",
                "derivatives",
                "chain_rule",
                "product_rule",
                "quotient_rule",
                "integrals",
                "integration_by_parts",
                "substitution",
            ]
        },
        "geometry": {
            "name": "Геометрия",
            "subskills": [
                "triangles",
                "circles",
                "vectors",
                "coordinate_geometry",
                "trigonometry",
            ]
        },
        "programming": {
            "name": "Программирование",
            "subskills": [
                "variables",
                "loops",
                "functions",
                "recursion",
                "oop",
                "algorithms",
                "data_structures",
            ]
        }
    }
    
    SKILL_PARAMS = {
        "easy": BKTParams(p_init=0.4, p_learn=0.15, p_guess=0.3, p_slip=0.1),
        "medium": BKTParams(p_init=0.3, p_learn=0.1, p_guess=0.25, p_slip=0.1),
        "hard": BKTParams(p_init=0.2, p_learn=0.08, p_guess=0.2, p_slip=0.15),
    }
    
    def __init__(self, student_id: str):
        self.student_id = student_id
        self.skills: Dict[str, SkillState] = {}
        self.params: Dict[str, BKTParams] = {}
        self.session_history: List[dict] = []
        self._initialize_skills()
    
    def _initialize_skills(self):
        """Инициализация всех навыков."""
        for category, data in self.SKILL_TAXONOMY.items():
            self.skills[category] = SkillState(name=data["name"])
            self.params[category] = self.SKILL_PARAMS["medium"]
            
            for subskill in data["subskills"]:
                self.skills[subskill] = SkillState(name=subskill)
                self.params[subskill] = self.SKILL_PARAMS["medium"]
    
    def update(self, skill: str, is_correct: bool, 
               hints_used: int = 0, time_spent: float = 0) -> float:
        """
        Обновить знание навыка после попытки.
        
        Returns: Новый уровень mastery
        """
        if skill not in self.skills:
            self.skills[skill] = SkillState(name=skill)
            self.params[skill] = self.SKILL_PARAMS["medium"]
        
        state = self.skills[skill]
        params = self.params[skill]
        
        # Корректируем с учётом подсказок
        if is_correct and hints_used > 0:
            hint_penalty = min(hints_used * 0.15, 0.5)
            params = BKTParams(
                p_init=params.p_init,
                p_learn=params.p_learn * (1 - hint_penalty),
                p_forget=params.p_forget,
                p_guess=params.p_guess + hint_penalty * 0.5,
                p_slip=params.p_slip
            )
        
        # BKT Update
        old_mastery = state.mastery
        new_mastery = self._bkt_update(old_mastery, is_correct, params)
        
        # Обновляем состояние
        state.mastery = new_mastery
        state.attempts += 1
        if is_correct:
            state.successes += 1
        state.last_attempt = datetime.now()
        state.history.append(is_correct)
        
        self._update_parent_skill(skill)
        
        self.session_history.append({
            "timestamp": datetime.now().isoformat(),
            "skill": skill,
            "is_correct": is_correct,
            "hints_used": hints_used,
            "old_mastery": old_mastery,
            "new_mastery": new_mastery
        })
        
        return new_mastery
    
    def _bkt_update(self, p_mastery: float, is_correct: bool, 
                    params: BKTParams) -> float:
        """Байесовское обновление вероятности знания."""
        p_l = p_mastery
        
        if is_correct:
            p_correct_given_l = 1 - params.p_slip
            p_correct_given_not_l = params.p_guess
            p_correct = p_correct_given_l * p_l + p_correct_given_not_l * (1 - p_l)
            
            if p_correct > 0:
                p_l_given_obs = (p_correct_given_l * p_l) / p_correct
            else:
                p_l_given_obs = p_l
        else:
            p_incorrect_given_l = params.p_slip
            p_incorrect_given_not_l = 1 - params.p_guess
            p_incorrect = p_incorrect_given_l * p_l + p_incorrect_given_not_l * (1 - p_l)
            
            if p_incorrect > 0:
                p_l_given_obs = (p_incorrect_given_l * p_l) / p_incorrect
            else:
                p_l_given_obs = p_l
        
        # Применяем обучение
        p_l_new = p_l_given_obs + (1 - p_l_given_obs) * params.p_learn
        p_l_new = p_l_new * (1 - params.p_forget)
        
        return max(0.01, min(0.99, p_l_new))
    
    def _update_parent_skill(self, skill: str):
        """Обновить mastery родительской категории."""
        for category, data in self.SKILL_TAXONOMY.items():
            if skill in data["subskills"]:
                subskill_masteries = [
                    self.skills[s].mastery 
                    for s in data["subskills"] 
                    if s in self.skills
                ]
                if subskill_masteries:
                    self.skills[category].mastery = sum(subskill_masteries) / len(subskill_masteries)
                break
    
    def get_mastery(self, skill: str) -> float:
        """Получить уровень знания навыка."""
        return self.skills[skill].mastery if skill in self.skills else 0.3
    
    def get_weakest_skills(self, n: int = 3) -> List[Tuple[str, float]]:
        """Получить N самых слабых навыков."""
        active = [(name, s.mastery) for name, s in self.skills.items() if s.attempts > 0]
        if not active:
            return [(name, s.mastery) for name, s in list(self.skills.items())[:n]]
        return sorted(active, key=lambda x: x[1])[:n]
    
    def get_strongest_skills(self, n: int = 3) -> List[Tuple[str, float]]:
        """Получить N самых сильных навыков."""
        active = [(name, s.mastery) for name, s in self.skills.items() if s.attempts > 0]
        return sorted(active, key=lambda x: x[1], reverse=True)[:n]
    
    def get_recommended_skill(self) -> str:
        """Рекомендовать навык для следующей задачи."""
        candidates = []
        
        for name, state in self.skills.items():
            is_category = name in self.SKILL_TAXONOMY
            if is_category:
                continue
                
            m = state.mastery
            
            if 0.4 <= m <= 0.7:
                priority = 1
            elif 0.3 <= m < 0.4:
                priority = 2
            elif 0.7 < m <= 0.85:
                priority = 3
            else:
                priority = 4
            
            candidates.append((name, m, priority, state.attempts))
        
        if not candidates:
            return "derivatives"
        
        candidates.sort(key=lambda x: (x[2], x[3], x[1]))
        return candidates[0][0]
    
    def get_recommended_difficulty(self, skill: str) -> str:
        """Рекомендовать сложность для навыка."""
        m = self.get_mastery(skill)
        
        if m < 0.4:
            return "easy"
        elif m < 0.6:
            return "medium"
        elif m < 0.8:
            return "hard"
        return "olympiad"
    
    def get_summary(self) -> dict:
        """Получить сводку по всем навыкам."""
        return {
            "student_id": self.student_id,
            "total_attempts": sum(s.attempts for s in self.skills.values()),
            "total_successes": sum(s.successes for s in self.skills.values()),
            "weakest": self.get_weakest_skills(3),
            "strongest": self.get_strongest_skills(3),
            "recommended_next": self.get_recommended_skill()
        }
    
    def to_dict(self) -> dict:
        """Сериализация."""
        return {
            "student_id": self.student_id,
            "skills": {
                name: {
                    "mastery": state.mastery,
                    "attempts": state.attempts,
                    "successes": state.successes,
                    "history": state.history[-50:]
                }
                for name, state in self.skills.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeTracer":
        """Десериализация."""
        tracer = cls(data["student_id"])
        for name, skill_data in data.get("skills", {}).items():
            if name in tracer.skills:
                tracer.skills[name].mastery = skill_data["mastery"]
                tracer.skills[name].attempts = skill_data["attempts"]
                tracer.skills[name].successes = skill_data["successes"]
                tracer.skills[name].history = skill_data.get("history", [])
        return tracer


def format_mastery_bar(mastery: float, width: int = 10) -> str:
    """Визуализация mastery."""
    filled = int(mastery * width)
    if mastery < 0.4:
        bar = "🟥" * filled + "⬜" * (width - filled)
    elif mastery < 0.7:
        bar = "🟨" * filled + "⬜" * (width - filled)
    else:
        bar = "🟩" * filled + "⬜" * (width - filled)
    return f"{bar} {mastery:.0%}"
