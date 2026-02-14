"""
MITS Coding Interface — Интерфейс для программирования

Включает:
- Банк алгоритмических задач
- Редактор кода
- Автоматическую проверку на тестах
- Умные подсказки по ошибкам
"""

import gradio as gr
from typing import Optional, Tuple, List, Dict, Any
import json

from src.models.llm_client import LLMClient
from src.models.prompts import UNIVERSAL_TUTOR_SYSTEM
from src.data.algo_task_bank import AlgorithmicTaskBank, Difficulty, Category
from src.execution.code_executor import CodeExecutor, ExecutionStatus, ErrorAnalyzer
from src.execution.code_analyzer import CodeAnalyzer, SolutionComparer
from src.utils.session_logger import SessionLogger
from src.config import settings


# Промпт для помощи с кодом
CODE_TUTOR_SYSTEM = """Ты — сократический репетитор по программированию и алгоритмам.

## ТВОЯ РОЛЬ:
Помогать студенту решить алгоритмическую задачу через наводящие вопросы.
НЕ давай готовый код! Направляй к решению.

## ФОРМАТИРОВАНИЕ:
- Код: ```python ... ```
- Формулы: $O(n)$, $O(n \\log n)$

## СТРАТЕГИИ:
1. Если студент не знает с чего начать → спроси про входные данные и что нужно получить
2. Если есть ошибка → укажи на тип ошибки, но не исправляй напрямую
3. Если неоптимально → спроси про сложность, предложи подумать о структурах данных
4. Если почти правильно → поддержи и укажи на мелочи

## ФОРМАТ ОТВЕТА:
{
    "move": "scaffolding|hint|rectify|encourage",
    "message": "Ответ на русском",
    "reasoning": "Скрытое обоснование"
}

ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ!"""


CODE_HELP_PROMPT = """## ЗАДАЧА:
{problem}

## КОД СТУДЕНТА:
```python
{code}
```

## РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ:
Статус: {status}
{execution_details}

## ИСТОРИЯ ДИАЛОГА:
{history}

## СООБЩЕНИЕ СТУДЕНТА:
{message}

Помоги студенту, но НЕ давай готовый код. Используй сократический метод.
Ответь в JSON: move, message, reasoning"""


class CodingApp:
    """Приложение для решения алгоритмических задач."""
    
    def __init__(self):
        self.llm_client: Optional[LLMClient] = None
        self.task_bank: Optional[AlgorithmicTaskBank] = None
        self.executor: Optional[CodeExecutor] = None
        self.analyzer: Optional[CodeAnalyzer] = None
        self.logger: Optional[SessionLogger] = None
        
        self.is_initialized = False
        self.current_task = None
        self.last_result = None
    
    def initialize(self) -> str:
        """Инициализация."""
        try:
            self.llm_client = LLMClient()
            
            if not self.llm_client.check_connection():
                return "❌ Ollama не запущен. Выполните: `ollama serve`"
            
            self.task_bank = AlgorithmicTaskBank()
            self.executor = CodeExecutor(timeout_seconds=5.0)
            self.analyzer = CodeAnalyzer()
            self.logger = SessionLogger()
            
            self.is_initialized = True
            
            stats = self.task_bank.get_stats()
            
            return f"""✅ **Система готова!**

🤖 Модель: `{settings.MODEL_NAME}`
📚 Задач: {stats['total']}
  • 🟢 Easy: {stats['by_difficulty']['easy']}
  • 🟡 Medium: {stats['by_difficulty']['medium']}
  • 🔴 Hard: {stats['by_difficulty']['hard']}"""
            
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"
    
    def get_task(self, task_id: str) -> Tuple[str, str, str]:
        """Получить задачу по ID."""
        if not self.is_initialized:
            return "⚠️ Система не инициализирована", "", ""
        
        task = self.task_bank.get_task(task_id)
        if not task:
            return f"❌ Задача '{task_id}' не найдена", "", ""
        
        self.current_task = task
        
        # Стартовый шаблон кода
        template = f'''# {task.title_ru}
# Сложность: {task._diff_ru()}

# Читаем входные данные
# ...

# Ваше решение:


# Выводим результат
# print(...)
'''
        
        return task.get_problem_text(), template, ""
    
    def get_random_task(self, difficulty: str, category: str) -> Tuple[str, str, str]:
        """Получить случайную задачу."""
        if not self.is_initialized:
            return "⚠️ Система не инициализирована", "", ""
        
        diff = Difficulty(difficulty) if difficulty != "any" else None
        cat = Category(category) if category != "any" else None
        
        task = self.task_bank.get_random_task(difficulty=diff, category=cat)
        
        if not task:
            return "❌ Задачи не найдены", "", ""
        
        return self.get_task(task.id)
    
    def run_code(self, code: str) -> str:
        """Запустить код на примерах."""
        if not self.current_task:
            return "⚠️ Сначала выберите задачу"
        
        if not code.strip():
            return "⚠️ Введите код"
        
        # Запускаем на видимых тестах
        visible_tests = self.current_task.get_visible_tests()
        
        if not visible_tests:
            # Берём из примеров
            from src.execution.code_executor import TestCase
            visible_tests = [
                TestCase(ex["input"], ex["output"])
                for ex in self.current_task.examples
            ]
        
        result = self.executor.run_tests(code, visible_tests, stop_on_first_fail=True)
        self.last_result = result
        
        output = f"## 🧪 Результаты тестирования\n\n"
        output += f"**Пройдено:** {result.passed}/{result.total}\n\n"
        
        for i, res in enumerate(result.results, 1):
            if res.is_correct:
                output += f"✅ **Тест {i}:** Пройден ({res.execution_time_ms:.0f} мс)\n"
            else:
                output += f"❌ **Тест {i}:** {res.status.value}\n"
                
                if res.status == ExecutionStatus.WRONG_ANSWER:
                    output += f"  • Ожидалось: `{res.expected[:50]}{'...' if len(res.expected) > 50 else ''}`\n"
                    output += f"  • Получено: `{res.output[:50]}{'...' if len(res.output) > 50 else ''}`\n"
                elif res.status == ExecutionStatus.RUNTIME_ERROR:
                    # Анализируем ошибку
                    analysis = ErrorAnalyzer.analyze(res.error)
                    output += f"  • **{analysis['type']}**\n"
                    output += f"  • 💡 {analysis['hint']}\n"
                    if analysis['example']:
                        output += f"  • Пример: `{analysis['example'][:60]}`\n"
                elif res.status == ExecutionStatus.TIME_LIMIT:
                    output += f"  • ⏱️ Программа работает слишком долго\n"
                    output += f"  • 💡 Оптимизируйте алгоритм\n"
                
                break
        
        return output
    
    def submit_code(self, code: str) -> str:
        """Отправить код на проверку всех тестов."""
        if not self.current_task:
            return "⚠️ Сначала выберите задачу"
        
        if not code.strip():
            return "⚠️ Введите код"
        
        # Запускаем на ВСЕХ тестах
        result = self.executor.run_tests(code, self.current_task.test_cases)
        self.last_result = result
        
        # Записываем попытку
        self.task_bank.record_attempt(self.current_task.id, result.is_accepted)
        
        if result.is_accepted:
            output = f"""## 🎉 ACCEPTED!

**Все тесты пройдены!** ✅ {result.passed}/{result.total}

Отличная работа! Вы решили задачу **{self.current_task.title_ru}**

### Статистика:
- Средне время: {sum(r.execution_time_ms for r in result.results) / len(result.results):.0f} мс
"""
        else:
            output = f"""## ❌ Неверный ответ

**Пройдено:** {result.passed}/{result.total}

"""
            if result.first_failed:
                res = result.first_failed
                if not res.is_correct and res.test_number > len(self.current_task.examples):
                    output += f"**Ошибка на скрытом тесте #{res.test_number}**\n\n"
                    output += "💡 Проверьте граничные случаи и ограничения\n"
                else:
                    output += f"**Ошибка на тесте #{res.test_number}**\n\n"
                    
                    if res.status == ExecutionStatus.WRONG_ANSWER:
                        analysis = ErrorAnalyzer.analyze_wrong_answer(
                            res.output, res.expected
                        )
                        for hint in analysis.get("hints", []):
                            output += f"• {hint}\n"
        
        return output
    
    def analyze_code(self, code: str) -> str:
        """Анализ кода студента."""
        if not code.strip():
            return "⚠️ Введите код для анализа"
        
        analysis = self.analyzer.analyze(code)
        
        output = "## 📊 Анализ кода\n\n"
        output += analysis["summary"] + "\n\n"
        
        # Проблемы
        if analysis["issues"]:
            output += "### 🔍 Найденные проблемы:\n\n"
            output += self.analyzer.get_formatted_issues() + "\n\n"
        
        # Сравнение с эталоном
        if self.current_task and self.current_task.solution_code:
            comparison = SolutionComparer.compare(code, self.current_task.solution_code)
            output += "### 📈 Сравнение с эталоном:\n\n"
            output += f"- Ваша сложность: {comparison['student_complexity']}\n"
            output += f"- Эталонная: {comparison['reference_complexity']}\n"
            output += f"- {comparison['feedback']}\n"
        
        return output
    
    def get_hint(self) -> str:
        """Получить подсказку."""
        if not self.current_task:
            return "⚠️ Сначала выберите задачу"
        
        hints = self.current_task.hints
        if not hints:
            return "💡 Подсказок для этой задачи нет"
        
        # Простая логика: возвращаем следующую подсказку
        # В реальности нужно отслеживать использованные
        return f"💡 **Подсказка:**\n\n{hints[0]}"
    
    def show_solution(self) -> Tuple[str, str]:
        """Показать решение."""
        if not self.current_task:
            return "⚠️ Сначала выберите задачу", ""
        
        explanation = self.current_task.solution_explanation or "Решение задачи"
        code = self.current_task.solution_code
        
        return f"## 📖 Решение\n\n{explanation}", code
    
    def ask_help(self, code: str, message: str, history: List) -> Tuple[str, List]:
        """Попросить помощи у AI."""
        if not self.is_initialized:
            return "", history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": "⚠️ Система не инициализирована"}
            ]
        
        if not message.strip():
            return "", history
        
        # Формируем контекст
        problem = self.current_task.get_problem_text() if self.current_task else "Задача не выбрана"
        
        exec_details = ""
        if self.last_result:
            exec_details = f"Пройдено тестов: {self.last_result.passed}/{self.last_result.total}\n"
            if self.last_result.first_failed:
                exec_details += f"Ошибка: {self.last_result.first_failed.status.value}\n"
                if self.last_result.first_failed.error:
                    exec_details += f"Сообщение: {self.last_result.first_failed.error[:200]}\n"
        
        history_text = "\n".join([
            f"{'Студент' if m['role'] == 'user' else 'Репетитор'}: {m['content']}"
            for m in history[-6:]
        ])
        
        prompt = CODE_HELP_PROMPT.format(
            problem=problem[:1000],
            code=code[:1500] if code else "Код не написан",
            status=self.last_result.status.value if self.last_result else "Не запускался",
            execution_details=exec_details,
            history=history_text or "Начало диалога",
            message=message
        )
        
        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system=CODE_TUTOR_SYSTEM,
                json_mode=True,
                thinking=True
            )
            
            try:
                data = json.loads(response)
                tutor_msg = data.get("message", response)
                move = data.get("move", "scaffolding")
                
                emoji = {"scaffolding": "🎯", "hint": "💡", "rectify": "📝", "encourage": "⭐"}.get(move, "")
                formatted = f"{emoji} {tutor_msg}"
            except:
                formatted = response
            
            new_history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": formatted}
            ]
            
            return "", new_history
            
        except Exception as e:
            return "", history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": f"❌ Ошибка: {str(e)}"}
            ]
    
    def get_task_list(self) -> str:
        """Получить список задач."""
        if not self.task_bank:
            return "Система не инициализирована"
        
        output = "## 📚 Список задач\n\n"
        
        for diff in [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD]:
            tasks = self.task_bank.get_tasks_by_difficulty(diff)
            emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}[diff.value]
            name = {"easy": "Лёгкие", "medium": "Средние", "hard": "Сложные"}[diff.value]
            
            output += f"### {emoji} {name} ({len(tasks)})\n\n"
            
            for task in tasks:
                rate = f"{task.acceptance_rate:.0%}" if task.attempts > 0 else "—"
                output += f"- `{task.id}` — **{task.title_ru}** ({task._cat_ru()}) [{rate}]\n"
            
            output += "\n"
        
        return output


# Создаём экземпляр
app = CodingApp()


def create_interface() -> gr.Blocks:
    """Создать интерфейс."""
    
    with gr.Blocks(title="🐝 MITS Coding") as interface:
        
        gr.Markdown("""
# 🐝 MITS — Алгоритмические задачи

**Решайте задачи в стиле LeetCode с умным помощником!**
        """)
        
        with gr.Row():
            status = gr.Textbox(
                label="📡 Статус",
                value="Нажмите 'Запустить'",
                interactive=False,
                scale=4
            )
            init_btn = gr.Button("🚀 Запустить", variant="primary", scale=1)
        
        with gr.Tabs():
            # === Вкладка: Решение задач ===
            with gr.Tab("💻 Решение задач"):
                with gr.Row():
                    # Левая панель: условие
                    with gr.Column(scale=1):
                        gr.Markdown("### 📋 Задача")
                        
                        with gr.Row():
                            diff_select = gr.Dropdown(
                                label="Сложность",
                                choices=[
                                    ("Любая", "any"),
                                    ("🟢 Easy", "easy"),
                                    ("🟡 Medium", "medium"),
                                    ("🔴 Hard", "hard")
                                ],
                                value="easy",
                                scale=1
                            )
                            cat_select = gr.Dropdown(
                                label="Категория",
                                choices=[
                                    ("Любая", "any"),
                                    ("Массивы", "arrays"),
                                    ("Строки", "strings"),
                                    ("Математика", "math"),
                                    ("Сортировка", "sorting"),
                                    ("Поиск", "searching"),
                                    ("Рекурсия", "recursion"),
                                    ("ДП", "dynamic_programming"),
                                    ("Хэш-таблицы", "hash_table"),
                                ],
                                value="any",
                                scale=1
                            )
                        
                        random_btn = gr.Button("🎲 Случайная задача", variant="primary")
                        
                        task_id_input = gr.Textbox(
                            label="Или введите ID задачи",
                            placeholder="two_sum, fibonacci, ..."
                        )
                        load_btn = gr.Button("📥 Загрузить")
                        
                        problem_display = gr.Markdown(
                            value="*Выберите задачу*",
                            label="Условие"
                        )
                        
                        with gr.Row():
                            hint_btn = gr.Button("💡 Подсказка", size="sm")
                            solution_btn = gr.Button("📖 Решение", size="sm")
                        
                        hint_output = gr.Markdown()
                    
                    # Правая панель: код и результаты
                    with gr.Column(scale=2):
                        gr.Markdown("### ✏️ Ваше решение")
                        
                        code_editor = gr.Code(
                            language="python",
                            label="Код",
                            lines=20,
                            value="# Введите ваше решение здесь\n"
                        )
                        
                        with gr.Row():
                            run_btn = gr.Button("▶️ Запустить", variant="secondary", scale=1)
                            analyze_btn = gr.Button("📊 Анализ", variant="secondary", scale=1)
                            submit_btn = gr.Button("📤 Отправить", variant="primary", scale=1)
                        
                        results_display = gr.Markdown(
                            value="*Результаты появятся здесь*",
                            label="Результаты"
                        )
                        
                        # Решение (скрытое)
                        solution_code = gr.Code(
                            language="python",
                            label="Решение автора",
                            visible=False
                        )
            
            # === Вкладка: Помощь AI ===
            with gr.Tab("🤖 Помощь AI"):
                gr.Markdown("*Задайте вопрос по текущей задаче или коду*")
                
                chatbot = gr.Chatbot(
                    value=[],
                    height=400,
                    show_label=False,
                    latex_delimiters=[
                        {"left": "$", "right": "$", "display": False},
                    ]
                )
                
                with gr.Row():
                    help_input = gr.Textbox(
                        label="Ваш вопрос",
                        placeholder="Не понимаю как подойти к задаче...",
                        scale=5
                    )
                    help_btn = gr.Button("📤", variant="primary", scale=1)
            
            # === Вкладка: Каталог ===
            with gr.Tab("📚 Каталог задач"):
                task_list = gr.Markdown("*Нажмите 'Обновить' для загрузки*")
                refresh_list_btn = gr.Button("🔄 Обновить список")
        
        # === Обработчики ===
        
        init_btn.click(fn=app.initialize, outputs=[status])
        
        # Загрузка задачи
        random_btn.click(
            fn=app.get_random_task,
            inputs=[diff_select, cat_select],
            outputs=[problem_display, code_editor, results_display]
        )
        
        load_btn.click(
            fn=app.get_task,
            inputs=[task_id_input],
            outputs=[problem_display, code_editor, results_display]
        )
        
        # Запуск и отправка
        run_btn.click(
            fn=app.run_code,
            inputs=[code_editor],
            outputs=[results_display]
        )
        
        analyze_btn.click(
            fn=app.analyze_code,
            inputs=[code_editor],
            outputs=[results_display]
        )
        
        submit_btn.click(
            fn=app.submit_code,
            inputs=[code_editor],
            outputs=[results_display]
        )
        
        # Подсказки
        hint_btn.click(
            fn=app.get_hint,
            outputs=[hint_output]
        )
        
        solution_btn.click(
            fn=app.show_solution,
            outputs=[hint_output, solution_code]
        ).then(
            fn=lambda: gr.update(visible=True),
            outputs=[solution_code]
        )
        
        # Помощь AI
        help_btn.click(
            fn=app.ask_help,
            inputs=[code_editor, help_input, chatbot],
            outputs=[help_input, chatbot]
        )
        
        help_input.submit(
            fn=app.ask_help,
            inputs=[code_editor, help_input, chatbot],
            outputs=[help_input, chatbot]
        )
        
        # Каталог
        refresh_list_btn.click(
            fn=app.get_task_list,
            outputs=[task_list]
        )
    
    return interface


if __name__ == "__main__":
    print("🐝 MITS Coding — Алгоритмические задачи")
    print(f"📡 Ollama: {settings.OLLAMA_HOST}")
    print(f"🤖 Модель: {settings.MODEL_NAME}")
    print()
    print("✨ Возможности:")
    print("   • 30 алгоритмических задач (Easy/Medium/Hard)")
    print("   • Автоматическая проверка на тестах")
    print("   • Анализ ошибок и подсказки")
    print("   • Сократический помощник")
    print()
    print("🌐 Откройте: http://localhost:7860")
    print()
    
    interface = create_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
