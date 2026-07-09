"""
Session Logger — Логирование учебных сессий

Сохраняет полную историю сессий для анализа и улучшения системы.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    """Сообщение в диалоге."""
    role: str  # "user" или "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Метаданные для сообщений тьютора
    tutor_move: Optional[str] = None  # scaffolding, hint, etc.
    is_telling: bool = False


@dataclass
class SessionLog:
    """Лог одной учебной сессии."""
    session_id: str
    student_id: str
    task_id: Optional[str] = None
    task_topic: Optional[str] = None
    task_difficulty: Optional[str] = None
    task_skills: List[str] = field(default_factory=list)

    messages: List[Message] = field(default_factory=list)

    # Результаты
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    duration_seconds: float = 0

    # Статистика
    total_attempts: int = 0
    hints_used: int = 0
    hints_available: int = 0

    # Финальный статус
    status: str = "in_progress"  # in_progress, solved, gave_up, told, timeout
    final_answer: Optional[str] = None
    is_correct: bool = False

    # Метаданные
    model_name: Optional[str] = None
    interface: str = "gradio"  # gradio, cli, api

    def add_message(
        self,
        role: str,
        content: str,
        tutor_move: Optional[str] = None,
        is_telling: bool = False
    ):
        """Добавить сообщение в лог."""
        msg = Message(
            role=role,
            content=content,
            tutor_move=tutor_move,
            is_telling=is_telling
        )
        self.messages.append(msg)

        if role == "user":
            self.total_attempts += 1

    def use_hint(self):
        """Записать использование подсказки."""
        self.hints_used += 1

    def end_session(self, status: str, final_answer: Optional[str] = None, is_correct: bool = False):
        """Завершить сессию."""
        self.ended_at = datetime.now()
        self.duration_seconds = (self.ended_at - self.started_at).total_seconds()
        self.status = status
        self.final_answer = final_answer
        self.is_correct = is_correct

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь."""
        return {
            "session_id": self.session_id,
            "student_id": self.student_id,
            "task_id": self.task_id,
            "task_topic": self.task_topic,
            "task_difficulty": self.task_difficulty,
            "task_skills": self.task_skills,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "tutor_move": m.tutor_move,
                    "is_telling": m.is_telling
                }
                for m in self.messages
            ],
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "total_attempts": self.total_attempts,
            "hints_used": self.hints_used,
            "hints_available": self.hints_available,
            "status": self.status,
            "final_answer": self.final_answer,
            "is_correct": self.is_correct,
            "model_name": self.model_name,
            "interface": self.interface
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionLog":
        """Десериализация из словаря."""
        log = cls(
            session_id=data["session_id"],
            student_id=data["student_id"]
        )
        log.task_id = data.get("task_id")
        log.task_topic = data.get("task_topic")
        log.task_difficulty = data.get("task_difficulty")
        log.task_skills = data.get("task_skills", [])

        for msg_data in data.get("messages", []):
            msg = Message(
                role=msg_data["role"],
                content=msg_data["content"],
                timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                tutor_move=msg_data.get("tutor_move"),
                is_telling=msg_data.get("is_telling", False)
            )
            log.messages.append(msg)

        log.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("ended_at"):
            log.ended_at = datetime.fromisoformat(data["ended_at"])

        log.duration_seconds = data.get("duration_seconds", 0)
        log.total_attempts = data.get("total_attempts", 0)
        log.hints_used = data.get("hints_used", 0)
        log.hints_available = data.get("hints_available", 0)
        log.status = data.get("status", "unknown")
        log.final_answer = data.get("final_answer")
        log.is_correct = data.get("is_correct", False)
        log.model_name = data.get("model_name")
        log.interface = data.get("interface", "unknown")

        return log


class SessionLogger:
    """
    Менеджер логирования сессий.
    
    Сохраняет логи в JSON файлы по дням.
    Поддерживает агрегированную аналитику.
    """

    def __init__(self, logs_dir: str = "./data/logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.active_sessions: Dict[str, SessionLog] = {}

    def start_session(
        self,
        student_id: str,
        task_id: Optional[str] = None,
        task_topic: Optional[str] = None,
        task_difficulty: Optional[str] = None,
        task_skills: Optional[List[str]] = None,
        hints_available: int = 3,
        model_name: Optional[str] = None,
        interface: str = "gradio"
    ) -> str:
        """
        Начать новую сессию.
        
        Возвращает session_id.
        """
        session_id = str(uuid.uuid4())

        log = SessionLog(
            session_id=session_id,
            student_id=student_id,
            task_id=task_id,
            task_topic=task_topic,
            task_difficulty=task_difficulty,
            task_skills=task_skills or [],
            hints_available=hints_available,
            model_name=model_name,
            interface=interface
        )

        self.active_sessions[session_id] = log
        return session_id

    def log_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tutor_move: Optional[str] = None,
        is_telling: bool = False
    ):
        """Записать сообщение в сессию."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].add_message(
                role=role,
                content=content,
                tutor_move=tutor_move,
                is_telling=is_telling
            )

    def log_hint(self, session_id: str):
        """Записать использование подсказки."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].use_hint()

    def end_session(
        self,
        session_id: str,
        status: str,
        final_answer: Optional[str] = None,
        is_correct: bool = False
    ):
        """Завершить и сохранить сессию."""
        if session_id not in self.active_sessions:
            return

        log = self.active_sessions[session_id]
        log.end_session(status, final_answer, is_correct)

        # Сохраняем в файл по дате
        date_str = log.started_at.strftime("%Y-%m-%d")
        filepath = self.logs_dir / f"sessions_{date_str}.jsonl"

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(log.to_dict(), ensure_ascii=False) + "\n")

        # Удаляем из активных
        del self.active_sessions[session_id]

    def get_session(self, session_id: str) -> Optional[SessionLog]:
        """Получить активную сессию."""
        return self.active_sessions.get(session_id)

    def load_sessions(
        self,
        date: Optional[datetime] = None,
        student_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[SessionLog]:
        """
        Загрузить сессии из логов.
        
        Args:
            date: Фильтр по дате (если None — все даты)
            student_id: Фильтр по студенту
            status: Фильтр по статусу
        """
        sessions = []

        if date:
            files = [self.logs_dir / f"sessions_{date.strftime('%Y-%m-%d')}.jsonl"]
        else:
            files = list(self.logs_dir.glob("sessions_*.jsonl"))

        for filepath in files:
            if not filepath.exists():
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    log = SessionLog.from_dict(data)

                    # Применяем фильтры
                    if student_id and log.student_id != student_id:
                        continue
                    if status and log.status != status:
                        continue

                    sessions.append(log)

        return sessions

    def get_analytics(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Получить агрегированную аналитику.
        
        Возвращает метрики:
        - Success@N: % задач решённых за N попыток
        - Telling@N: % сессий где дали ответ
        - Avg hints per session
        - Avg duration
        - По темам и сложности
        """
        sessions = self.load_sessions()

        if date_from:
            sessions = [s for s in sessions if s.started_at >= date_from]
        if date_to:
            sessions = [s for s in sessions if s.started_at <= date_to]

        if not sessions:
            return {"error": "Нет данных для анализа"}

        total = len(sessions)
        solved = sum(1 for s in sessions if s.status == "solved")
        told = sum(1 for s in sessions if s.status == "told")
        gave_up = sum(1 for s in sessions if s.status == "gave_up")

        # Success@10: решено за <= 10 попыток
        success_10 = sum(
            1 for s in sessions
            if s.status == "solved" and s.total_attempts <= 10
        )

        # Telling@10: сказали ответ при <= 10 попытках
        telling_10 = sum(
            1 for s in sessions
            if s.status == "told" and s.total_attempts <= 10
        )

        avg_hints = sum(s.hints_used for s in sessions) / total if total > 0 else 0
        avg_duration = sum(s.duration_seconds for s in sessions) / total if total > 0 else 0
        avg_attempts = sum(s.total_attempts for s in sessions) / total if total > 0 else 0

        # По темам
        by_topic = {}
        for s in sessions:
            topic = s.task_topic or "unknown"
            if topic not in by_topic:
                by_topic[topic] = {"total": 0, "solved": 0}
            by_topic[topic]["total"] += 1
            if s.status == "solved":
                by_topic[topic]["solved"] += 1

        for topic in by_topic:
            t = by_topic[topic]
            t["success_rate"] = t["solved"] / t["total"] if t["total"] > 0 else 0

        return {
            "total_sessions": total,
            "solved": solved,
            "told": told,
            "gave_up": gave_up,
            "success_rate": solved / total if total > 0 else 0,
            "success_at_10": success_10 / total if total > 0 else 0,
            "telling_at_10": telling_10 / total if total > 0 else 0,
            "avg_hints_per_session": round(avg_hints, 2),
            "avg_duration_seconds": round(avg_duration, 1),
            "avg_attempts": round(avg_attempts, 1),
            "by_topic": by_topic
        }

    def get_student_stats(self, student_id: str) -> Dict[str, Any]:
        """Получить статистику по студенту."""
        sessions = self.load_sessions(student_id=student_id)

        if not sessions:
            return {"error": "Нет данных для этого студента"}

        total = len(sessions)
        solved = sum(1 for s in sessions if s.status == "solved")

        # Собираем навыки
        skills_practiced = {}
        for s in sessions:
            for skill in s.task_skills:
                if skill not in skills_practiced:
                    skills_practiced[skill] = {"total": 0, "solved": 0}
                skills_practiced[skill]["total"] += 1
                if s.status == "solved":
                    skills_practiced[skill]["solved"] += 1

        return {
            "total_sessions": total,
            "success_rate": solved / total if total > 0 else 0,
            "total_problems_solved": solved,
            "skills_practiced": skills_practiced,
            "avg_hints_per_session": sum(s.hints_used for s in sessions) / total,
            "total_time_minutes": sum(s.duration_seconds for s in sessions) / 60
        }
