"""
MITS Gradio Interface - Русская версия

Веб-интерфейс для системы сократического репетиторства.
"""

import gradio as gr
from typing import Optional, Tuple, List
import uuid

from src.models.llm_client import LLMClient
from src.agents.tutor_agent import SocraticTutorAgent
from src.agents.task_generator import TaskGeneratorAgent
from src.agents.response_verifier import ResponseVerifierAgent
from src.data.schemas import (
    Task, TutoringSession, Difficulty, Subject,
    ConversationTurn, TutorMove
)
from src.config import settings


# ═══════════════════════════════════════════════════════════════════════════
# Чёрно-жёлтая тема CSS
# ═══════════════════════════════════════════════════════════════════════════

CUSTOM_CSS = """
/* Основной фон */
.gradio-container {
    background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%) !important;
}

/* Заголовки */
h1, h2, h3, h4, h5, h6 {
    color: #FFD700 !important;
}

/* Текст */
.prose p, .prose li, label, .label-wrap span {
    color: #e0e0e0 !important;
}

/* Кнопки primary */
.primary {
    background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%) !important;
    color: #1a1a1a !important;
    border: none !important;
    font-weight: bold !important;
}

.primary:hover {
    background: linear-gradient(135deg, #FFE44D 0%, #FFB732 100%) !important;
    transform: translateY(-2px);
    box-shadow: 0 4px 15px rgba(255, 215, 0, 0.4) !important;
}

/* Кнопки secondary */
.secondary {
    background: #3a3a3a !important;
    color: #FFD700 !important;
    border: 2px solid #FFD700 !important;
}

.secondary:hover {
    background: #4a4a4a !important;
}

/* Текстовые поля */
textarea, input[type="text"] {
    background: #2a2a2a !important;
    color: #ffffff !important;
    border: 2px solid #444 !important;
}

textarea:focus, input[type="text"]:focus {
    border-color: #FFD700 !important;
    box-shadow: 0 0 10px rgba(255, 215, 0, 0.3) !important;
}

/* Dropdown */
.wrap select, .wrap input {
    background: #2a2a2a !important;
    color: #ffffff !important;
    border: 2px solid #444 !important;
}

/* Чат */
.chatbot {
    background: #1e1e1e !important;
    border: 2px solid #FFD700 !important;
    border-radius: 10px !important;
}

.message {
    border-radius: 10px !important;
}

.user {
    background: linear-gradient(135deg, #3a3a3a 0%, #2a2a2a 100%) !important;
    border: 1px solid #FFD700 !important;
}

.bot {
    background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%) !important;
    border: 1px solid #666 !important;
}

/* Панели */
.panel {
    background: #252525 !important;
    border: 1px solid #444 !important;
    border-radius: 10px !important;
}

/* Markdown блоки */
.prose {
    color: #e0e0e0 !important;
}

.prose code {
    background: #3a3a3a !important;
    color: #FFD700 !important;
}

/* Статус */
.status-success {
    color: #4CAF50 !important;
}

.status-error {
    color: #f44336 !important;
}

/* Разделители */
hr {
    border-color: #FFD700 !important;
    opacity: 0.3;
}

/* Скроллбар */
::-webkit-scrollbar {
    width: 8px;
}

::-webkit-scrollbar-track {
    background: #1a1a1a;
}

::-webkit-scrollbar-thumb {
    background: #FFD700;
    border-radius: 4px;
}

/* Акцентные элементы */
.accent {
    color: #FFD700 !important;
}

/* Блок с информацией о задаче */
.task-info {
    background: #2a2a2a !important;
    border-left: 4px solid #FFD700 !important;
    padding: 10px !important;
    border-radius: 5px !important;
}
"""


# ═══════════════════════════════════════════════════════════════════════════
# Русские сообщения
# ═══════════════════════════════════════════════════════════════════════════

WELCOME_MESSAGE_RU = """🎓 **Добро пожаловать!** Давайте решим эту задачу вместе.

**📝 Задача:**

{problem}

---

Подумайте над задачей. Какой у вас первый подход к решению?"""

SUCCESS_MESSAGE_RU = """🎉 **Отлично! Вы решили задачу!**

**Ваш ответ:** {student_answer}

Правильно! Вы показали отличные навыки решения задач. 

Хотите попробовать ещё одну задачу?"""


class TutoringApp:
    """Основное приложение для управления сессиями репетиторства."""
    
    def __init__(self):
        self.llm_client: Optional[LLMClient] = None
        self.tutor: Optional[SocraticTutorAgent] = None
        self.task_generator: Optional[TaskGeneratorAgent] = None
        self.verifier: Optional[ResponseVerifierAgent] = None
        self.current_session: Optional[TutoringSession] = None
        self.is_initialized = False
    
    def initialize(self) -> str:
        """Инициализация LLM клиента и агентов."""
        try:
            self.llm_client = LLMClient()
            
            if not self.llm_client.check_connection():
                return "❌ Не удалось подключиться к Ollama. Запустите: ollama serve"
            
            models = self.llm_client.list_models()
            if not any(settings.MODEL_NAME.split(':')[0] in m for m in models):
                return f"❌ Модель {settings.MODEL_NAME} не найдена. Выполните: ollama pull {settings.MODEL_NAME}"
            
            self.tutor = SocraticTutorAgent(self.llm_client)
            self.task_generator = TaskGeneratorAgent(self.llm_client)
            self.verifier = ResponseVerifierAgent(self.llm_client)
            
            self.is_initialized = True
            return f"✅ Система инициализирована! Модель: {settings.MODEL_NAME}"
            
        except Exception as e:
            return f"❌ Ошибка инициализации: {str(e)}"
    
    def start_session(
        self,
        topic: str,
        difficulty: str,
        custom_problem: str = ""
    ) -> Tuple[str, str, List]:
        """Начать новую сессию репетиторства."""
        if not self.is_initialized:
            return "⚠️ Сначала инициализируйте систему!", "", []
        
        try:
            difficulty_enum = Difficulty(difficulty)
            
            if custom_problem.strip():
                task = Task(
                    id=str(uuid.uuid4()),
                    topic=topic,
                    difficulty=difficulty_enum,
                    problem=custom_problem,
                    solution="Пользовательская задача - решение не предоставлено",
                    answer="[Пользовательская]",
                    skills=[topic]
                )
            else:
                task = self.task_generator.generate_task(
                    topic=topic,
                    difficulty=difficulty_enum
                )
            
            self.current_session = TutoringSession(
                id=str(uuid.uuid4()),
                student_id="gradio_user",
                task=task
            )
            
            welcome = WELCOME_MESSAGE_RU.format(problem=task.problem)
            
            # Перевод сложности
            diff_ru = {
                "easy": "Лёгкий", "medium": "Средний", 
                "hard": "Сложный", "olympiad": "Олимпиадный"
            }
            
            # Перевод темы
            topic_ru = {
                "derivatives": "Производные", "integrals": "Интегралы",
                "limits": "Пределы", "linear_equations": "Линейные уравнения",
                "quadratic_equations": "Квадратные уравнения",
                "chain_rule": "Цепное правило", "product_rule": "Правило произведения",
                "quotient_rule": "Правило частного", "trigonometry": "Тригонометрия",
                "vectors": "Векторы"
            }
            
            task_info = f"""**📚 Тема:** {topic_ru.get(topic, topic)}
**📊 Сложность:** {diff_ru.get(difficulty, difficulty)}
**🎯 Навыки:** {', '.join(task.skills)}
**💡 Подсказок доступно:** {len(task.hints)}"""
            
            return "", task_info, [{"role": "assistant", "content": welcome}]
            
        except Exception as e:
            return f"❌ Ошибка создания сессии: {str(e)}", "", []
    
    def process_message(
        self,
        message: str,
        history: List
    ) -> Tuple[str, List]:
        """Обработать сообщение студента."""
        if not self.current_session:
            return "⚠️ Сначала начните сессию!", history
        
        if not message.strip():
            return "", history
        
        try:
            self.current_session.add_student_message(message)
            
            verification = self.verifier.verify(
                self.current_session.task,
                message
            )
            
            if verification.is_correct:
                self.current_session.is_solved = True
                success_msg = SUCCESS_MESSAGE_RU.format(student_answer=message)
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": success_msg})
                return "", history
            
            response = self.tutor.generate_response(
                session=self.current_session,
                student_message=message,
                verification_result=verification
            )
            
            self.current_session.add_tutor_response(response)
            
            move_emoji = {
                TutorMove.SCAFFOLDING: "🎯",
                TutorMove.PROBLEMATIZE: "🤔",
                TutorMove.RECTIFY: "📝",
                TutorMove.ENCOURAGE: "⭐",
                TutorMove.HINT: "💡",
                TutorMove.TELL: "📖"
            }
            
            emoji = move_emoji.get(response.move, "")
            formatted_response = f"{emoji} {response.message}"
            
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": formatted_response})
            return "", history
            
        except Exception as e:
            error_msg = f"❌ Ошибка: {str(e)}"
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": error_msg})
            return "", history
    
    def get_hint(self) -> str:
        """Получить подсказку."""
        if not self.current_session:
            return "⚠️ Сначала начните сессию!"
        
        task = self.current_session.task
        hints_used = self.current_session.hints_used
        
        if hints_used >= len(task.hints):
            return "❌ Подсказки закончились!"
        
        hint = task.hints[hints_used]
        self.current_session.hints_used += 1
        
        return f"💡 **Подсказка {hints_used + 1}/{len(task.hints)}:** {hint}"
    
    def show_solution(self) -> str:
        """Показать решение."""
        if not self.current_session:
            return "⚠️ Сначала начните сессию!"
        
        task = self.current_session.task
        self.current_session.told_answer = True
        
        return f"""## 📖 Решение

{task.solution}

**✅ Ответ:** {task.answer}

---
⚠️ *Эта сессия помечена как "ответ показан" для статистики.*"""
    
    def get_session_stats(self) -> str:
        """Получить статистику сессии."""
        if not self.current_session:
            return "📊 Нет активной сессии"
        
        session = self.current_session
        
        status = '✅ Решено!' if session.is_solved else '🔄 В процессе'
        revealed = '⚠️ Да' if session.told_answer else '✅ Нет'
        
        return f"""## 📊 Статистика сессии

| Параметр | Значение |
|----------|----------|
| **Попыток** | {session.attempts} |
| **Подсказок использовано** | {session.hints_used}/{len(session.task.hints)} |
| **Сообщений** | {len(session.conversation)} |
| **Статус** | {status} |
| **Ответ показан** | {revealed} |"""


# Создаём экземпляр приложения
app = TutoringApp()


def create_interface() -> gr.Blocks:
    """Создать интерфейс Gradio."""
    
    with gr.Blocks() as interface:
        
        gr.Markdown("""
# 🐝 MITS — Интеллектуальный Репетитор по Математике

**Сократический метод обучения:** Я не даю готовые ответы, а помогаю вам 
самостоятельно прийти к решению через наводящие вопросы!
        """)
        
        # Статус системы
        with gr.Row():
            status_text = gr.Textbox(
                label="🔌 Статус системы",
                value="Нажмите 'Запустить систему' для начала",
                interactive=False
            )
            init_btn = gr.Button("🚀 Запустить систему", variant="primary")
        
        with gr.Row():
            # Левая колонка - Управление
            with gr.Column(scale=1):
                gr.Markdown("### 📚 Новая задача")
                
                topic_dropdown = gr.Dropdown(
                    choices=[
                        ("Производные", "derivatives"),
                        ("Интегралы", "integrals"),
                        ("Пределы", "limits"),
                        ("Линейные уравнения", "linear_equations"),
                        ("Квадратные уравнения", "quadratic_equations"),
                        ("Цепное правило", "chain_rule"),
                        ("Правило произведения", "product_rule"),
                        ("Правило частного", "quotient_rule"),
                        ("Тригонометрия", "trigonometry"),
                        ("Векторы", "vectors")
                    ],
                    value="derivatives",
                    label="Тема"
                )
                
                difficulty_dropdown = gr.Dropdown(
                    choices=[
                        ("Лёгкий", "easy"),
                        ("Средний", "medium"),
                        ("Сложный", "hard"),
                        ("Олимпиадный", "olympiad")
                    ],
                    value="medium",
                    label="Сложность"
                )
                
                custom_problem = gr.Textbox(
                    label="Своя задача (опционально)",
                    placeholder="Введите свою задачу или оставьте пустым для автогенерации...",
                    lines=2
                )
                
                start_btn = gr.Button("▶️ Начать задачу", variant="primary")
                
                gr.Markdown("### 📋 Текущая задача")
                task_info = gr.Markdown("*Задача не выбрана*")
                
                gr.Markdown("### 🛠️ Инструменты")
                hint_btn = gr.Button("💡 Подсказка", variant="secondary")
                hint_output = gr.Markdown()
                
                solution_btn = gr.Button("📖 Показать решение", variant="secondary")
                solution_output = gr.Markdown()
                
                stats_btn = gr.Button("📊 Статистика", variant="secondary")
                stats_output = gr.Markdown()
            
            # Правая колонка - Чат
            with gr.Column(scale=2):
                gr.Markdown("### 💬 Диалог с репетитором")
                
                chatbot = gr.Chatbot(
                    height=500,
                    show_label=False,
                    latex_delimiters=[
                        {"left": "$$", "right": "$$", "display": True},
                        {"left": "$", "right": "$", "display": False},
                        {"left": "\\[", "right": "\\]", "display": True},
                        {"left": "\\(", "right": "\\)", "display": False}
                    ]
                )
                
                with gr.Row():
                    msg_input = gr.Textbox(
                        label="Ваше сообщение",
                        placeholder="Напишите ваши мысли, вопросы или решение...",
                        lines=2,
                        scale=4
                    )
                    send_btn = gr.Button("📤 Отправить", variant="primary", scale=1)
        
        gr.Markdown("""
---
### 📖 Как пользоваться:

1. **Запустите систему** — подключение к языковой модели
2. **Выберите тему и сложность** — затем нажмите "Начать задачу"
3. **Пишите ваши идеи** — репетитор направит вас вопросами
4. **Используйте подсказки** — если совсем застряли
5. **Посмотрите решение** — для изучения после попыток

---
*🐝 Сократический метод помогает по-настоящему понять материал, а не просто запомнить!*
        """)
        
        # Обработчики событий
        init_btn.click(
            fn=app.initialize,
            outputs=[status_text]
        )
        
        start_btn.click(
            fn=app.start_session,
            inputs=[topic_dropdown, difficulty_dropdown, custom_problem],
            outputs=[msg_input, task_info, chatbot]
        )
        
        send_btn.click(
            fn=app.process_message,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot]
        )
        
        msg_input.submit(
            fn=app.process_message,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot]
        )
        
        hint_btn.click(fn=app.get_hint, outputs=[hint_output])
        solution_btn.click(fn=app.show_solution, outputs=[solution_output])
        stats_btn.click(fn=app.get_session_stats, outputs=[stats_output])
    
    return interface


# Точка входа
if __name__ == "__main__":
    print("🐝 Запуск MITS — Сократический Репетитор по Математике...")
    print(f"📡 Ollama: {settings.OLLAMA_HOST}")
    print(f"🤖 Модель: {settings.MODEL_NAME}")
    print()
    print("🌐 Откройте в браузере: http://localhost:7860")
    print()
    
    interface = create_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
