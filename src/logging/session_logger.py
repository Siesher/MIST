"""
Session Logger - Логирование учебных сессий

Структурированное сохранение всех данных сессий для анализа.

Feature 010: Extended with performance metrics for diploma.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import uuid


@dataclass
class SessionLog:
    """Полный лог сессии."""
    session_id: str
    student_id: str
    task_id: str
    task_topic: str
    task_difficulty: str
    task_problem: str
    task_answer: str

    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0.0

    is_solved: bool = False
    told_answer: bool = False
    hints_used: int = 0
    attempts: int = 0

    messages: List[Dict] = None
    skills_involved: List[str] = None
    final_mastery_delta: Dict[str, float] = None

    # Feature 010: Extended performance metrics
    total_response_time_ms: float = 0.0
    avg_response_time_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    total_tokens_used: int = 0
    peak_vram_mb: float = 0.0
    peak_ram_mb: float = 0.0
    ab_variant: Optional[str] = None
    few_shot_used: bool = False
    cot_used: bool = False
    compression_count: int = 0
    compression_ratio: float = 1.0

    def __post_init__(self):
        if self.messages is None:
            self.messages = []
        if self.skills_involved is None:
            self.skills_involved = []
        if self.final_mastery_delta is None:
            self.final_mastery_delta = {}

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class SessionLogger:
    """Логгер сессий с SQLite."""
    
    def __init__(self, db_path: str = "data/sessions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.current_sessions: Dict[str, SessionLog] = {}
    
    def _init_db(self):
        """Инициализация БД."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                student_id TEXT,
                task_id TEXT,
                task_topic TEXT,
                task_difficulty TEXT,
                task_problem TEXT,
                task_answer TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_seconds REAL,
                is_solved INTEGER,
                told_answer INTEGER,
                hints_used INTEGER,
                attempts INTEGER,
                messages_json TEXT,
                skills_json TEXT,
                mastery_delta_json TEXT,
                -- Feature 010: Performance metrics
                total_response_time_ms REAL DEFAULT 0.0,
                avg_response_time_ms REAL DEFAULT 0.0,
                cache_hits INTEGER DEFAULT 0,
                cache_misses INTEGER DEFAULT 0,
                total_tokens_used INTEGER DEFAULT 0,
                peak_vram_mb REAL DEFAULT 0.0,
                peak_ram_mb REAL DEFAULT 0.0,
                ab_variant TEXT,
                few_shot_used INTEGER DEFAULT 0,
                cot_used INTEGER DEFAULT 0,
                compression_count INTEGER DEFAULT 0,
                compression_ratio REAL DEFAULT 1.0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TEXT,
                role TEXT,
                content TEXT,
                tutor_move TEXT,
                is_correct INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date TEXT PRIMARY KEY,
                total_sessions INTEGER,
                sessions_solved INTEGER,
                sessions_told INTEGER,
                avg_hints REAL,
                avg_attempts REAL,
                avg_duration REAL,
                topics_json TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def start_session(
        self,
        student_id: str,
        task_id: str,
        task_topic: str,
        task_difficulty: str,
        task_problem: str,
        task_answer: str,
        skills: List[str] = None
    ) -> str:
        """Начать новую сессию."""
        session_id = str(uuid.uuid4())
        
        session = SessionLog(
            session_id=session_id,
            student_id=student_id,
            task_id=task_id,
            task_topic=task_topic,
            task_difficulty=task_difficulty,
            task_problem=task_problem,
            task_answer=task_answer,
            start_time=datetime.now().isoformat(),
            skills_involved=skills or []
        )
        
        self.current_sessions[session_id] = session
        return session_id
    
    def log_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tutor_move: Optional[str] = None,
        is_correct: Optional[bool] = None
    ):
        """Добавить сообщение."""
        if session_id not in self.current_sessions:
            return
        
        session = self.current_sessions[session_id]
        
        msg = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "tutor_move": tutor_move,
            "is_correct": is_correct
        }
        
        session.messages.append(msg)
        
        if role == "student":
            session.attempts += 1
    
    def log_hint(self, session_id: str):
        """Зафиксировать подсказку."""
        if session_id in self.current_sessions:
            self.current_sessions[session_id].hints_used += 1

    # Feature 010: Extended logging methods for performance metrics

    def log_response_time(self, session_id: str, response_time_ms: float):
        """Log response time for a message."""
        if session_id not in self.current_sessions:
            return

        session = self.current_sessions[session_id]
        session.total_response_time_ms += response_time_ms

        # Update average
        msg_count = len([m for m in session.messages if m.get("role") == "tutor"])
        if msg_count > 0:
            session.avg_response_time_ms = session.total_response_time_ms / msg_count

    def log_cache_result(self, session_id: str, is_hit: bool):
        """Log cache hit or miss."""
        if session_id not in self.current_sessions:
            return

        session = self.current_sessions[session_id]
        if is_hit:
            session.cache_hits += 1
        else:
            session.cache_misses += 1

    def log_tokens(self, session_id: str, tokens: int):
        """Log tokens used."""
        if session_id in self.current_sessions:
            self.current_sessions[session_id].total_tokens_used += tokens

    def log_resource_usage(
        self,
        session_id: str,
        vram_mb: float = 0.0,
        ram_mb: float = 0.0
    ):
        """Log peak resource usage."""
        if session_id not in self.current_sessions:
            return

        session = self.current_sessions[session_id]
        session.peak_vram_mb = max(session.peak_vram_mb, vram_mb)
        session.peak_ram_mb = max(session.peak_ram_mb, ram_mb)

    def set_ab_variant(self, session_id: str, variant: str):
        """Set A/B test variant for session."""
        if session_id in self.current_sessions:
            self.current_sessions[session_id].ab_variant = variant

    def set_few_shot_used(self, session_id: str, used: bool = True):
        """Mark that few-shot prompting was used."""
        if session_id in self.current_sessions:
            self.current_sessions[session_id].few_shot_used = used

    def set_cot_used(self, session_id: str, used: bool = True):
        """Mark that Chain-of-Thought was used."""
        if session_id in self.current_sessions:
            self.current_sessions[session_id].cot_used = used

    def log_compression(self, session_id: str, compression_ratio: float):
        """Log context compression event."""
        if session_id not in self.current_sessions:
            return

        session = self.current_sessions[session_id]
        session.compression_count += 1
        session.compression_ratio = compression_ratio
    
    def end_session(
        self,
        session_id: str,
        is_solved: bool,
        told_answer: bool = False,
        mastery_delta: Dict[str, float] = None
    ):
        """Завершить и сохранить сессию."""
        if session_id not in self.current_sessions:
            return
        
        session = self.current_sessions[session_id]
        session.end_time = datetime.now().isoformat()
        session.is_solved = is_solved
        session.told_answer = told_answer
        session.final_mastery_delta = mastery_delta or {}
        
        start = datetime.fromisoformat(session.start_time)
        end = datetime.fromisoformat(session.end_time)
        session.duration_seconds = (end - start).total_seconds()
        
        self._save_session(session)
        self._update_daily_metrics(session)
        
        del self.current_sessions[session_id]
    
    def _save_session(self, session: SessionLog):
        """Сохранить в SQLite."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Feature 010: Extended with performance metrics
        cursor.execute("""
            INSERT OR REPLACE INTO sessions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            session.session_id,
            session.student_id,
            session.task_id,
            session.task_topic,
            session.task_difficulty,
            session.task_problem,
            session.task_answer,
            session.start_time,
            session.end_time,
            session.duration_seconds,
            int(session.is_solved),
            int(session.told_answer),
            session.hints_used,
            session.attempts,
            json.dumps(session.messages, ensure_ascii=False),
            json.dumps(session.skills_involved),
            json.dumps(session.final_mastery_delta),
            # Feature 010: Performance metrics
            session.total_response_time_ms,
            session.avg_response_time_ms,
            session.cache_hits,
            session.cache_misses,
            session.total_tokens_used,
            session.peak_vram_mb,
            session.peak_ram_mb,
            session.ab_variant,
            int(session.few_shot_used),
            int(session.cot_used),
            session.compression_count,
            session.compression_ratio
        ))

        conn.commit()
        conn.close()
    
    def _update_daily_metrics(self, session: SessionLog):
        """Обновить дневные метрики."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM daily_metrics WHERE date = ?", (today,))
        row = cursor.fetchone()
        
        if row:
            total = row[1] + 1
            solved = row[2] + (1 if session.is_solved else 0)
            told = row[3] + (1 if session.told_answer else 0)
            avg_hints = (row[4] * row[1] + session.hints_used) / total
            avg_attempts = (row[5] * row[1] + session.attempts) / total
            avg_duration = (row[6] * row[1] + session.duration_seconds) / total
            topics = json.loads(row[7])
            topics[session.task_topic] = topics.get(session.task_topic, 0) + 1
        else:
            total = 1
            solved = 1 if session.is_solved else 0
            told = 1 if session.told_answer else 0
            avg_hints = session.hints_used
            avg_attempts = session.attempts
            avg_duration = session.duration_seconds
            topics = {session.task_topic: 1}
        
        cursor.execute("""
            INSERT OR REPLACE INTO daily_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (today, total, solved, told, avg_hints, avg_attempts, avg_duration, json.dumps(topics)))
        
        conn.commit()
        conn.close()
    
    def get_metrics(self, days: int = 7) -> dict:
        """Получить метрики за N дней."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Feature 010: Extended metrics query
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(is_solved) as solved,
                SUM(told_answer) as told,
                AVG(hints_used) as avg_hints,
                AVG(attempts) as avg_attempts,
                AVG(duration_seconds) as avg_duration,
                AVG(avg_response_time_ms) as avg_response_time,
                SUM(cache_hits) as total_cache_hits,
                SUM(cache_misses) as total_cache_misses,
                AVG(total_tokens_used) as avg_tokens,
                AVG(peak_vram_mb) as avg_vram,
                AVG(peak_ram_mb) as avg_ram,
                SUM(few_shot_used) as few_shot_count,
                SUM(cot_used) as cot_count,
                AVG(compression_ratio) as avg_compression_ratio
            FROM sessions
            WHERE date(start_time) >= date('now', ?)
        """, (f"-{days} days",))

        row = cursor.fetchone()
        conn.close()

        total = row[0] or 0
        solved = row[1] or 0
        told = row[2] or 0
        cache_hits = row[7] or 0
        cache_misses = row[8] or 0
        total_cache = cache_hits + cache_misses

        return {
            "period_days": days,
            "total_sessions": total,
            "success_rate": solved / total if total > 0 else 0,
            "telling_rate": told / total if total > 0 else 0,
            "avg_hints": row[3] or 0,
            "avg_attempts": row[4] or 0,
            "avg_duration_seconds": row[5] or 0,
            # Feature 010: Performance metrics
            "avg_response_time_ms": row[6] or 0,
            "cache_hit_rate": cache_hits / total_cache if total_cache > 0 else 0,
            "total_cache_hits": cache_hits,
            "total_cache_misses": cache_misses,
            "avg_tokens_per_session": row[9] or 0,
            "avg_peak_vram_mb": row[10] or 0,
            "avg_peak_ram_mb": row[11] or 0,
            "few_shot_usage_rate": (row[12] or 0) / total if total > 0 else 0,
            "cot_usage_rate": (row[13] or 0) / total if total > 0 else 0,
            "avg_compression_ratio": row[14] or 1.0,
        }
    
    def export_to_json(self, output_path: str):
        """Экспорт в JSON."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions")
        rows = cursor.fetchall()
        conn.close()
        
        sessions = []
        for row in rows:
            sessions.append({
                "session_id": row[0],
                "student_id": row[1],
                "task_id": row[2],
                "task_topic": row[3],
                "task_difficulty": row[4],
                "is_solved": bool(row[10]),
                "told_answer": bool(row[11]),
                "hints_used": row[12],
                "attempts": row[13],
                "duration_seconds": row[9]
            })
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
        
        print(f"📊 Экспортировано {len(sessions)} сессий")
