"""
MITS Gradio Interface v2 — С улучшениями

- Knowledge Tracing (отслеживание знаний)
- Банк задач (мгновенный выбор)
- Streaming ответов
- Логирование сессий
"""

import gradio as gr
from typing import Optional, Tuple, List, Generator
import json
import uuid

from src.models.llm_client import LLMClient
from src.models.knowledge_tracing import KnowledgeTracker, StudentModel
from src.models.prompts import (
    UNIVERSAL_TUTOR_SYSTEM, 
    UNIVERSAL_RESPONSE_PROMPT,
    WELCOME_MESSAGE_UNIVERSAL
)
from src.data.task_bank import TaskBank
from src.utils.session_logger import SessionLogger
from src.config import settings


class MITSApp:
    """
    Главное приложение MITS с улучшениями.
    """
    
    def __init__(self):
        self.llm_client: Optional[LLMClient] = None
        self.knowledge_tracker: Optional[KnowledgeTracker] = None
        self.task_bank: Optional[TaskBank] = None
        self.session_logger: Optional[SessionLogger] = None
        
        self.is_initialized = False
        self.student_id = f"student_{uuid.uuid4().hex[:8]}"
        self.current_session_id: Optional[str] = None
        self.current_task = None
    
    def initialize(self) -> str:
        """Инициализация всех компонентов."""
        try:
            # LLM
            self.llm_client = LLMClient()
            
            if not self.llm_client.check_connection():
                return "❌ Не удалось подключиться к Ollama. Запустите: `ollama serve`"
            
            models = self.llm_client.list_models()
            model_base = settings.MODEL_NAME.split(':')[0]
            if not any(model_base in m for m in models):
                return f"❌ Модель {settings.MODEL_NAME} не найдена. Выполните: `ollama pull {settings.MODEL_NAME}`"
            
            # Knowledge Tracker
            self.knowledge_tracker = KnowledgeTracker()
            
            # Task Bank
            self.task_bank = TaskBank()
            bank_stats = self.task_bank.get_stats_summary()
            
            # Session Logger
            self.session_logger = SessionLogger()
            
            self.is_initialized = True
            
            return f"""✅ **Система готова!**

🤖 Модель: `{settings.MODEL_NAME}`
📚 Задач в банке: {bank_stats['total_tasks']}
🎯 Тем: {len(bank_stats['topics'])}
📊 Навыков: {bank_stats['skills_count']}"""
            
        except Exception as e:
            return f"❌ Ошибка инициализации: {str(e)}"
    
    def start_task_from_bank(
        self,
        topic: str,
        difficulty: str,
        history: List
    ) -> Tuple[str, str, List]:
        """Начать задачу из банка."""
        if not self.is_initialized:
            return "⚠️ Сначала запустите систему!", "", history
        
        # Получаем модель студента
        student = self.knowledge_tracker.get_student(self.student_id)
        
        # Выбираем задачу
        if topic == "adaptive":
            # Адаптивный выбор на основе знаний
            skill_masteries = {s: skill.mastery for s, skill in student.skills.items()}
            task = self.task_bank.get_adaptive_task(skill_masteries)
        else:
            task = self.task_bank.get_task(
                topic=topic if topic != "any" else None,
                difficulty=difficulty if difficulty != "any" else None
            )
        
        if not task:
            return "❌ Задачи по этим критериям не найдены", "", history
        
        self.current_task = task
        
        # Начинаем сессию логирования
        diff_val = task.difficulty.value if hasattr(task.difficulty, 'value') else task.difficulty
        self.current_session_id = self.session_logger.start_session(
            student_id=self.student_id,
            task_id=task.id,
            task_topic=task.topic,
            task_difficulty=diff_val,
            task_skills=task.skills,
            hints_available=len(task.hints),
            model_name=settings.MODEL_NAME
        )
        
        # Формируем приветствие
        welcome = f"""🎯 **Новая задача!**

**📝 Условие:**

{task.problem}

---

С чего начнём решение?"""
        
        # Инфо о задаче
        topic_ru = {
            "derivatives": "Производные",
            "integrals": "Интегралы", 
            "limits": "Пределы",
            "equations": "Уравнения",
            "programming": "Программирование"
        }
        diff_ru = {
            "easy": "Лёгкий",
            "medium": "Средний",
            "hard": "Сложный",
            "olympiad": "Олимпиадный"
        }
        
        task_info = f"""**📚 Тема:** {topic_ru.get(task.topic, task.topic)}
**📊 Сложность:** {diff_ru.get(diff_val, diff_val)}
**🎯 Навыки:** {', '.join(task.skills)}
**💡 Подсказок:** {len(task.hints)}"""
        
        new_history = [{"role": "assistant", "content": welcome}]
        
        return "", task_info, new_history
    
    def chat(
        self,
        message: str,
        history: List
    ) -> Tuple[str, List]:
        """Обработка сообщения со streaming."""
        if not self.is_initialized:
            error_msg = "⚠️ Сначала нажмите 'Запустить систему'!"
            return "", history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": error_msg}
            ]
        
        if not message.strip():
            return "", history
        
        # Логируем сообщение пользователя
        if self.current_session_id:
            self.session_logger.log_message(
                self.current_session_id,
                role="user",
                content=message
            )
        
        try:
            # Формируем историю для промпта
            history_text = ""
            for msg in history[-10:]:
                role = "Студент" if msg["role"] == "user" else "Репетитор"
                history_text += f"{role}: {msg['content']}\n"
            
            # Генерируем ответ
            prompt = UNIVERSAL_RESPONSE_PROMPT.format(
                conversation_history=history_text if history_text else "Начало диалога",
                student_message=message
            )
            
            response = self.llm_client.generate(
                prompt=prompt,
                system=UNIVERSAL_TUTOR_SYSTEM,
                json_mode=True,
                thinking=True
            )
            
            # Парсим JSON
            try:
                data = json.loads(response)
                tutor_message = data.get("message", response)
                move = data.get("move", "scaffolding")
                is_telling = (move == "tell")
                
                move_emoji = {
                    "scaffolding": "🎯",
                    "problematize": "🤔", 
                    "rectify": "📝",
                    "encourage": "⭐",
                    "hint": "💡",
                    "tell": "📖"
                }
                emoji = move_emoji.get(move, "")
                formatted_response = f"{emoji} {tutor_message}"
                
            except json.JSONDecodeError:
                formatted_response = response
                move = "unknown"
                is_telling = False
            
            # Логируем ответ тьютора
            if self.current_session_id:
                self.session_logger.log_message(
                    self.current_session_id,
                    role="assistant",
                    content=formatted_response,
                    tutor_move=move,
                    is_telling=is_telling
                )
            
            # Обновляем знания если это задача из банка
            if self.current_task and move == "encourage":
                # Возможно правильный ответ - обновляем mastery
                for skill in self.current_task.skills:
                    self.knowledge_tracker.record_attempt(
                        self.student_id,
                        skills=[skill],
                        is_correct=True
                    )
            
            new_history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": formatted_response}
            ]
            
            return "", new_history
            
        except Exception as e:
            error_msg = f"❌ Ошибка: {str(e)}"
            return "", history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": error_msg}
            ]
    
    def get_hint(self, history: List) -> Tuple[str, List]:
        """Получить подсказку."""
        if not self.current_task:
            return "⚠️ Сначала выберите задачу!", history
        
        session = self.session_logger.get_session(self.current_session_id) if self.current_session_id else None
        hints_used = session.hints_used if session else 0
        
        if hints_used >= len(self.current_task.hints):
            return "❌ Подсказки закончились!", history
        
        hint = self.current_task.hints[hints_used]
        
        # Логируем
        if self.current_session_id:
            self.session_logger.log_hint(self.current_session_id)
        
        hint_msg = f"💡 **Подсказка {hints_used + 1}/{len(self.current_task.hints)}:**\n\n{hint}"
        
        new_history = history + [{"role": "assistant", "content": hint_msg}]
        return "", new_history
    
    def show_solution(self, history: List) -> Tuple[str, List]:
        """Показать решение."""
        if not self.current_task:
            return "⚠️ Сначала выберите задачу!", history
        
        # Записываем что показали ответ
        if self.current_session_id:
            self.session_logger.end_session(
                self.current_session_id,
                status="told",
                is_correct=False
            )
        
        # Обновляем mastery (показали ответ = не решил)
        if self.current_task:
            for skill in self.current_task.skills:
                self.knowledge_tracker.record_attempt(
                    self.student_id,
                    skills=[skill],
                    is_correct=False
                )
        
        solution_msg = f"""📖 **Решение:**

{self.current_task.solution}

---

**Ответ:** {self.current_task.answer}"""
        
        new_history = history + [{"role": "assistant", "content": solution_msg}]
        return "", new_history
    
    def get_student_profile(self) -> str:
        """Получить профиль знаний студента."""
        if not self.knowledge_tracker:
            return "⚠️ Система не инициализирована"
        
        student = self.knowledge_tracker.get_student(self.student_id)
        return student.get_summary()
    
    def get_analytics(self) -> str:
        """Получить аналитику сессий."""
        if not self.session_logger:
            return "⚠️ Система не инициализирована"
        
        analytics = self.session_logger.get_analytics()
        
        if "error" in analytics:
            return f"📊 {analytics['error']}"
        
        return f"""📊 **Аналитика сессий:**

**Всего сессий:** {analytics['total_sessions']}
**Решено:** {analytics['solved']} ({analytics['success_rate']:.0%})
**Показан ответ:** {analytics['told']}
**Сдались:** {analytics['gave_up']}

**Метрики качества:**
• Success@10: {analytics['success_at_10']:.0%}
• Telling@10: {analytics['telling_at_10']:.0%}
• Среднее подсказок: {analytics['avg_hints_per_session']}
• Среднее время: {analytics['avg_duration_seconds']:.0f} сек
• Среднее попыток: {analytics['avg_attempts']}"""
    
    def clear_chat(self) -> Tuple[str, str, List]:
        """Очистить чат."""
        # Завершаем текущую сессию
        if self.current_session_id:
            self.session_logger.end_session(
                self.current_session_id,
                status="gave_up"
            )
        
        self.current_task = None
        self.current_session_id = None
        
        return "", "", [{"role": "assistant", "content": WELCOME_MESSAGE_UNIVERSAL}]


# Создаём экземпляр
app = MITSApp()


def create_interface() -> gr.Blocks:
    """Создать интерфейс Gradio."""
    
    with gr.Blocks(title="🐝 MITS - Сократический Репетитор") as interface:
        
        gr.Markdown("""
# 🐝 MITS — Умный Репетитор v2

**Сократический метод + Адаптивное обучение + Knowledge Tracing**
        """)
        
        with gr.Row():
            status = gr.Textbox(
                label="📡 Статус системы",
                value="Нажмите 'Запустить' для начала",
                interactive=False,
                scale=4
            )
            init_btn = gr.Button("🚀 Запустить", variant="primary", scale=1)
        
        with gr.Tabs():
            # Вкладка 1: Свободный диалог
            with gr.Tab("💬 Свободный диалог"):
                gr.Markdown("*Задайте любой вопрос или опишите задачу*")
                
                chatbot_free = gr.Chatbot(
                    value=[{"role": "assistant", "content": WELCOME_MESSAGE_UNIVERSAL}],
                    height=450,
                    show_label=False,
                    latex_delimiters=[
                        {"left": "$$", "right": "$$", "display": True},
                        {"left": "$", "right": "$", "display": False},
                    ]
                )
                
                with gr.Row():
                    msg_free = gr.Textbox(
                        label="💬 Сообщение",
                        placeholder="Напиши задачу или вопрос...",
                        lines=2,
                        scale=5
                    )
                    send_free = gr.Button("📤 Отправить", variant="primary", scale=1)
            
            # Вкладка 2: Задачи из банка
            with gr.Tab("📚 Задачи из банка"):
                with gr.Row():
                    with gr.Column(scale=1):
                        topic_select = gr.Dropdown(
                            label="📚 Тема",
                            choices=[
                                ("🎯 Адаптивный выбор", "adaptive"),
                                ("📐 Любая тема", "any"),
                                ("∂ Производные", "derivatives"),
                                ("∫ Интегралы", "integrals"),
                                ("→ Пределы", "limits"),
                                ("= Уравнения", "equations"),
                                ("💻 Программирование", "programming")
                            ],
                            value="adaptive"
                        )
                        diff_select = gr.Dropdown(
                            label="📊 Сложность",
                            choices=[
                                ("Любая", "any"),
                                ("🟢 Лёгкий", "easy"),
                                ("🟡 Средний", "medium"),
                                ("🟠 Сложный", "hard"),
                                ("🔴 Олимпиадный", "olympiad")
                            ],
                            value="any"
                        )
                        start_task_btn = gr.Button("🎲 Получить задачу", variant="primary")
                        
                        task_info = gr.Markdown("*Нажмите 'Получить задачу'*")
                        
                        with gr.Row():
                            hint_btn = gr.Button("💡 Подсказка", variant="secondary")
                            solution_btn = gr.Button("📖 Решение", variant="secondary")
                    
                    with gr.Column(scale=2):
                        chatbot_task = gr.Chatbot(
                            value=[],
                            height=400,
                            show_label=False,
                            latex_delimiters=[
                                {"left": "$$", "right": "$$", "display": True},
                                {"left": "$", "right": "$", "display": False},
                            ]
                        )
                        
                        with gr.Row():
                            msg_task = gr.Textbox(
                                label="💬 Ваш ответ",
                                placeholder="Напишите решение или вопрос...",
                                lines=2,
                                scale=5
                            )
                            send_task = gr.Button("📤", variant="primary", scale=1)
            
            # Вкладка 3: Профиль знаний
            with gr.Tab("📊 Мой профиль"):
                profile_output = gr.Markdown("*Нажмите 'Обновить' для просмотра профиля*")
                refresh_profile_btn = gr.Button("🔄 Обновить профиль")
                
                analytics_output = gr.Markdown("")
                refresh_analytics_btn = gr.Button("📈 Показать аналитику")
        
        with gr.Row():
            clear_btn = gr.Button("🗑️ Новый диалог", variant="secondary")
        
        # === Обработчики ===
        
        init_btn.click(fn=app.initialize, outputs=[status])
        
        # Свободный диалог
        send_free.click(
            fn=app.chat,
            inputs=[msg_free, chatbot_free],
            outputs=[msg_free, chatbot_free]
        )
        msg_free.submit(
            fn=app.chat,
            inputs=[msg_free, chatbot_free],
            outputs=[msg_free, chatbot_free]
        )
        
        # Задачи из банка
        start_task_btn.click(
            fn=app.start_task_from_bank,
            inputs=[topic_select, diff_select, chatbot_task],
            outputs=[msg_task, task_info, chatbot_task]
        )
        
        send_task.click(
            fn=app.chat,
            inputs=[msg_task, chatbot_task],
            outputs=[msg_task, chatbot_task]
        )
        msg_task.submit(
            fn=app.chat,
            inputs=[msg_task, chatbot_task],
            outputs=[msg_task, chatbot_task]
        )
        
        hint_btn.click(
            fn=app.get_hint,
            inputs=[chatbot_task],
            outputs=[msg_task, chatbot_task]
        )
        
        solution_btn.click(
            fn=app.show_solution,
            inputs=[chatbot_task],
            outputs=[msg_task, chatbot_task]
        )
        
        # Профиль
        refresh_profile_btn.click(
            fn=app.get_student_profile,
            outputs=[profile_output]
        )
        
        refresh_analytics_btn.click(
            fn=app.get_analytics,
            outputs=[analytics_output]
        )
        
        # Очистка
        clear_btn.click(
            fn=app.clear_chat,
            outputs=[msg_free, task_info, chatbot_free]
        )
    
    return interface


if __name__ == "__main__":
    print("🐝 MITS v2 — Сократический Репетитор с улучшениями")
    print(f"📡 Ollama: {settings.OLLAMA_HOST}")
    print(f"🤖 Модель: {settings.MODEL_NAME}")
    print()
    print("✨ Улучшения:")
    print("   • Knowledge Tracing (отслеживание знаний)")
    print("   • Банк задач (мгновенный выбор)")
    print("   • Логирование сессий")
    print("   • Адаптивный выбор задач")
    print()
    print("🌐 Откройте: http://localhost:7860")
    print()
    
    interface = create_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
