"""
MITS Synthetic Dialog Generator

Generates synthetic Socratic tutoring dialogs using Nemotron-3-Nano-30B-A3B
as the Teacher model for knowledge distillation.
"""

import json
import uuid
import random
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Generator
from enum import Enum
from pathlib import Path
import structlog

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.llm_client import LLMClient
from src.data.schemas import Task, TutorMove, Difficulty, Subject
from src.config import settings

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════
# Enums and Data Classes
# ═══════════════════════════════════════════════════════════════════════════

class StudentPersona(str, Enum):
    """Simulated student types for diverse dialog generation."""
    NOVICE = "novice"           # Makes basic errors, needs scaffolding
    INTERMEDIATE = "intermediate"  # Partial understanding, detail errors
    ADVANCED = "advanced"       # Good understanding, subtle errors
    CONFUSED = "confused"       # Frustrated, needs encouragement
    CURIOUS = "curious"         # Asks why questions


@dataclass
class DialogTurn:
    """Single turn in a tutoring dialog."""
    role: str                   # "student" or "tutor"
    content: str                # Message content
    move: Optional[str] = None  # Teaching move (tutor only)
    reasoning: Optional[str] = None  # Internal reasoning (tutor only)

    def to_dict(self) -> Dict[str, Any]:
        d = {"role": self.role, "content": self.content}
        if self.move:
            d["move"] = self.move
        if self.reasoning:
            d["reasoning"] = self.reasoning
        return d


@dataclass
class SyntheticDialog:
    """Complete synthetic tutoring dialog."""
    id: str
    task: Dict[str, Any]
    student_persona: str
    turns: List[DialogTurn] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task": self.task,
            "student_persona": self.student_persona,
            "turns": [t.to_dict() for t in self.turns],
            "metadata": self.metadata
        }

    def to_training_format(self) -> Dict[str, Any]:
        """Convert to training format with conversations."""
        messages = []

        # Build task context for system message
        task_context = f"""ЗАДАЧА:
Условие: {self.task.get('problem', '')}
Тема: {self.task.get('topic', '')}
Сложность: {self.task.get('difficulty', '')}

СПРАВКА (НЕ раскрывай студенту):
Решение: {self.task.get('solution', '')}
Ответ: {self.task.get('answer', '')}
Подсказки: {self.task.get('hints', [])}"""

        system_prompt = f"""{SYSTEM_PROMPT}

{task_context}"""

        messages.append({"role": "system", "content": system_prompt})

        for turn in self.turns:
            if turn.role == "student":
                messages.append({"role": "user", "content": turn.content})
            else:
                # Tutor response in JSON format
                response = {
                    "move": turn.move or "scaffolding",
                    "message": turn.content,
                    "reasoning": turn.reasoning or ""
                }
                messages.append({
                    "role": "assistant",
                    "content": json.dumps(response, ensure_ascii=False, indent=2)
                })

        return {
            "id": self.id,
            "conversations": messages,
            "task_topic": self.task.get("topic", ""),
            "task_difficulty": self.task.get("difficulty", ""),
            "student_persona": self.student_persona,
            "num_turns": len(self.turns)
        }


# ═══════════════════════════════════════════════════════════════════════════
# Prompts
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Ты — сократический репетитор по математике. Твоя миссия — помогать студентам самостоятельно находить решения через наводящие вопросы.

ПРИНЦИПЫ:
1. НИКОГДА не давай готовых ответов сразу
2. Задавай ОДИН чёткий вопрос за раз
3. Используй $LaTeX$ для математики: $x^2$, $\\frac{a}{b}$, $\\sqrt{x}$
4. Отвечай на русском языке

ТИПЫ ХОДОВ (move):
- scaffolding: Разбить на шаги, направить вопросом
- problematize: Спросить "почему?" или "что если?"
- rectify: Мягко указать на ошибку
- encourage: Похвалить прогресс
- hint: Дать подсказку (если студент застрял)
- tell: Раскрыть ответ (ТОЛЬКО в крайнем случае!)

ФОРМАТ ОТВЕТА (JSON):
{
    "move": "scaffolding",
    "message": "Твой ответ студенту с $LaTeX$",
    "reasoning": "Внутреннее обоснование (скрыто от студента)"
}"""

STUDENT_SIMULATION_PROMPT = """Ты симулируешь студента типа "{persona}" решающего математическую задачу.

ЗАДАЧА: {problem}

ПРЕДЫДУЩИЙ ДИАЛОГ:
{dialog_history}

ПОСЛЕДНИЙ ОТВЕТ РЕПЕТИТОРА: {tutor_message}

Характеристики студента "{persona}":
- novice: Не понимает базовые концепции, делает простые ошибки, часто говорит "не понимаю"
- intermediate: Частично понимает, ошибается в деталях, иногда угадывает
- advanced: Хорошо понимает, делает тонкие ошибки, задаёт умные вопросы
- confused: Расстроен, просит помощи, говорит "запутался", "не получается"
- curious: Спрашивает "почему?", "а что если?", хочет понять глубже

Сгенерируй ОДИН естественный ответ студента (1-3 предложения).
НЕ пиши ничего кроме ответа студента. Без кавычек, без пояснений."""

TUTOR_GENERATION_PROMPT = """КОНТЕКСТ ЗАДАЧИ:
Условие: {problem}
Правильное решение: {solution}
Ответ: {answer}
Типичные ошибки: {common_mistakes}
Доступные подсказки: {hints}

ИСТОРИЯ ДИАЛОГА:
{dialog_history}

СООБЩЕНИЕ СТУДЕНТА: {student_message}

ТЕКУЩЕЕ СОСТОЯНИЕ:
- Попытки студента: {attempts}
- Использовано подсказок: {hints_used}/{max_hints}
- Тип студента: {student_persona}

Сгенерируй ответ репетитора в формате JSON:
{{
    "move": "scaffolding|problematize|rectify|encourage|hint|tell",
    "message": "Ответ с $LaTeX$ формулами",
    "reasoning": "Почему выбран этот ход"
}}

ВАЖНО:
- Если студент решил задачу верно → move: "encourage"
- Если студент сделал ошибку → move: "rectify"
- Если студент застрял → move: "hint" или "scaffolding"
- move: "tell" только если hints_used >= max_hints и студент полностью застрял"""


# ═══════════════════════════════════════════════════════════════════════════
# Dialog Generator
# ═══════════════════════════════════════════════════════════════════════════

class SyntheticDialogGenerator:
    """
    Generates synthetic Socratic tutoring dialogs using Teacher model.
    """

    # Distribution of teaching moves in generated dialogs
    MOVE_DISTRIBUTION = {
        TutorMove.SCAFFOLDING: 0.35,
        TutorMove.PROBLEMATIZE: 0.20,
        TutorMove.RECTIFY: 0.15,
        TutorMove.ENCOURAGE: 0.15,
        TutorMove.HINT: 0.10,
        TutorMove.TELL: 0.05
    }

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        model: str = None
    ):
        """
        Initialize generator.

        Args:
            llm_client: LLM client instance (creates default if None)
            model: Model name override
        """
        self.llm = llm_client or LLMClient(model=model)
        logger.info("dialog_generator_initialized", model=self.llm.model)

    def generate_dialog(
        self,
        task: Task,
        student_persona: StudentPersona = None,
        min_turns: int = 4,
        max_turns: int = 10,
        target_solved: bool = True
    ) -> SyntheticDialog:
        """
        Generate a complete synthetic tutoring dialog.

        Args:
            task: Math task to tutor on
            student_persona: Type of student to simulate
            min_turns: Minimum dialog turns
            max_turns: Maximum dialog turns
            target_solved: Whether student should eventually solve

        Returns:
            SyntheticDialog with generated turns
        """
        if student_persona is None:
            student_persona = random.choice(list(StudentPersona))

        dialog = SyntheticDialog(
            id=str(uuid.uuid4()),
            task={
                "problem": task.problem,
                "solution": task.solution,
                "answer": task.answer,
                "topic": task.topic,
                "difficulty": task.difficulty.value,
                "hints": task.hints,
                "common_mistakes": task.common_mistakes
            },
            student_persona=student_persona.value
        )

        attempts = 0
        hints_used = 0
        max_hints = len(task.hints)

        # Generate initial student message
        initial_messages = [
            "Не понимаю с чего начать",
            "Как решать эту задачу?",
            "Можете помочь?",
            f"Мне нужно найти {task.topic}, но я не знаю как",
            "Я попробовал, но не получается"
        ]
        student_msg = random.choice(initial_messages)
        dialog.turns.append(DialogTurn(role="student", content=student_msg))

        for turn_num in range(max_turns):
            # Generate tutor response
            tutor_response = self._generate_tutor_response(
                task=task,
                dialog=dialog,
                student_message=student_msg,
                attempts=attempts,
                hints_used=hints_used,
                max_hints=max_hints,
                student_persona=student_persona
            )

            if tutor_response is None:
                logger.warning("tutor_generation_failed", turn=turn_num)
                break

            dialog.turns.append(tutor_response)

            # Check if we should end dialog
            if tutor_response.move == "tell":
                # Task revealed, end dialog
                break

            if tutor_response.move == "encourage" and "правильно" in tutor_response.content.lower():
                # Task solved
                break

            if turn_num >= min_turns - 1 and target_solved:
                # After min turns, increase chance of solving
                if random.random() < 0.3:
                    # Student solves
                    student_msg = f"Понял! Ответ: {task.answer}"
                    dialog.turns.append(DialogTurn(role="student", content=student_msg))
                    # Final encouragement
                    final_response = DialogTurn(
                        role="tutor",
                        content=f"Отлично! ${task.answer}$ — верный ответ! Молодец, что разобрался самостоятельно.",
                        move="encourage",
                        reasoning="Student solved the task correctly"
                    )
                    dialog.turns.append(final_response)
                    break

            # Generate next student message
            student_msg = self._generate_student_message(
                task=task,
                dialog=dialog,
                tutor_message=tutor_response.content,
                student_persona=student_persona
            )

            if student_msg is None:
                logger.warning("student_generation_failed", turn=turn_num)
                break

            dialog.turns.append(DialogTurn(role="student", content=student_msg))

            # Update counters
            attempts += 1
            if tutor_response.move == "hint":
                hints_used += 1

        # Add metadata
        dialog.metadata = {
            "num_turns": len(dialog.turns),
            "hints_used": hints_used,
            "attempts": attempts,
            "solved": any(
                t.move == "encourage" and "правильно" in t.content.lower()
                for t in dialog.turns if t.role == "tutor"
            ),
            "told_answer": any(t.move == "tell" for t in dialog.turns if t.role == "tutor")
        }

        logger.info(
            "dialog_generated",
            dialog_id=dialog.id,
            turns=len(dialog.turns),
            persona=student_persona.value,
            solved=dialog.metadata["solved"]
        )

        return dialog

    def _generate_tutor_response(
        self,
        task: Task,
        dialog: SyntheticDialog,
        student_message: str,
        attempts: int,
        hints_used: int,
        max_hints: int,
        student_persona: StudentPersona
    ) -> Optional[DialogTurn]:
        """Generate tutor response using LLM."""

        # Build dialog history
        history = "\n".join([
            f"{'Студент' if t.role == 'student' else 'Репетитор'}: {t.content}"
            for t in dialog.turns[-6:]  # Last 6 turns for context
        ])

        prompt = TUTOR_GENERATION_PROMPT.format(
            problem=task.problem,
            solution=task.solution,
            answer=task.answer,
            common_mistakes=", ".join(task.common_mistakes) or "нет данных",
            hints=task.hints,
            dialog_history=history or "Начало диалога",
            student_message=student_message,
            attempts=attempts,
            hints_used=hints_used,
            max_hints=max_hints,
            student_persona=student_persona.value
        )

        try:
            response = self.llm.generate(
                prompt=prompt,
                system=SYSTEM_PROMPT,
                json_mode=True,
                thinking=True,
                temperature=0.7
            )

            # Parse JSON response
            data = json.loads(response)

            return DialogTurn(
                role="tutor",
                content=data.get("message", ""),
                move=data.get("move", "scaffolding"),
                reasoning=data.get("reasoning", "")
            )

        except json.JSONDecodeError as e:
            logger.error("json_parse_error", error=str(e), response=response[:200])
            return None
        except Exception as e:
            logger.error("tutor_generation_error", error=str(e))
            return None

    def _generate_student_message(
        self,
        task: Task,
        dialog: SyntheticDialog,
        tutor_message: str,
        student_persona: StudentPersona
    ) -> Optional[str]:
        """Generate student response using LLM."""

        history = "\n".join([
            f"{'Студент' if t.role == 'student' else 'Репетитор'}: {t.content}"
            for t in dialog.turns[-6:]
        ])

        prompt = STUDENT_SIMULATION_PROMPT.format(
            persona=student_persona.value,
            problem=task.problem,
            dialog_history=history or "Начало диалога",
            tutor_message=tutor_message
        )

        try:
            response = self.llm.generate(
                prompt=prompt,
                thinking=False,  # Student doesn't need thinking
                temperature=0.8  # More variability
            )

            # Clean up response
            response = response.strip().strip('"').strip("'")
            return response

        except Exception as e:
            logger.error("student_generation_error", error=str(e))
            return None

    def generate_batch(
        self,
        tasks: List[Task],
        dialogs_per_task: int = 3,
        personas: List[StudentPersona] = None
    ) -> Generator[SyntheticDialog, None, None]:
        """
        Generate batch of dialogs for multiple tasks.

        Args:
            tasks: List of tasks
            dialogs_per_task: Number of dialogs to generate per task
            personas: Student personas to use (cycles through if fewer than dialogs_per_task)

        Yields:
            SyntheticDialog instances
        """
        if personas is None:
            personas = list(StudentPersona)

        total = len(tasks) * dialogs_per_task
        generated = 0

        for task in tasks:
            for i in range(dialogs_per_task):
                persona = personas[i % len(personas)]

                try:
                    dialog = self.generate_dialog(
                        task=task,
                        student_persona=persona
                    )
                    generated += 1
                    logger.info("batch_progress", current=generated, total=total)
                    yield dialog

                except Exception as e:
                    logger.error(
                        "dialog_generation_failed",
                        task_id=task.id,
                        persona=persona.value,
                        error=str(e)
                    )
                    continue


# ═══════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════

def save_dialogs(
    dialogs: List[SyntheticDialog],
    output_path: Path,
    format: str = "jsonl"
) -> None:
    """
    Save dialogs to file.

    Args:
        dialogs: List of dialogs
        output_path: Output file path
        format: "jsonl" or "json"
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "jsonl":
        with open(output_path, "w", encoding="utf-8") as f:
            for dialog in dialogs:
                f.write(json.dumps(dialog.to_dict(), ensure_ascii=False) + "\n")
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                [d.to_dict() for d in dialogs],
                f,
                ensure_ascii=False,
                indent=2
            )

    logger.info("dialogs_saved", path=str(output_path), count=len(dialogs))


def save_training_data(
    dialogs: List[SyntheticDialog],
    output_path: Path
) -> None:
    """
    Save dialogs in training format (JSONL with conversations).

    Args:
        dialogs: List of dialogs
        output_path: Output file path
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for dialog in dialogs:
            training_sample = dialog.to_training_format()
            f.write(json.dumps(training_sample, ensure_ascii=False) + "\n")

    logger.info("training_data_saved", path=str(output_path), count=len(dialogs))


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Example usage
    from src.data.task_bank import TaskBank

    # Initialize
    generator = SyntheticDialogGenerator()
    task_bank = TaskBank()

    # Get sample task
    tasks = task_bank.get_tasks(limit=2)

    if tasks:
        # Generate dialog
        dialog = generator.generate_dialog(
            task=tasks[0],
            student_persona=StudentPersona.NOVICE
        )

        print("\n" + "="*60)
        print(f"Dialog ID: {dialog.id}")
        print(f"Task: {dialog.task['problem'][:50]}...")
        print(f"Persona: {dialog.student_persona}")
        print("="*60)

        for turn in dialog.turns:
            role = "Student" if turn.role == "student" else f"Tutor [{turn.move}]"
            print(f"\n{role}:")
            print(turn.content)

        print("\n" + "="*60)
        print(f"Metadata: {dialog.metadata}")
