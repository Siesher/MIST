"""
MITS Unified — Единый интерфейс для математики и программирования

Объединяет все возможности системы:
- Математические задачи с Knowledge Tracing
- Алгоритмические задачи с автопроверкой
- Свободный диалог с AI
- Профиль знаний студента
- Dual-Memory System (Session + Student)
- Cognitive Load Monitoring

UI: Claude-style design (Feature 008-claude-ui-redesign)
"""

import gradio as gr
from typing import Optional, List, Dict, Any, Tuple
import json
import uuid
from pathlib import Path

from src.models.llm_client import LLMClient
from src.models.prompts import (
    UNIVERSAL_TUTOR_SYSTEM,
    UNIVERSAL_RESPONSE_PROMPT,
    WELCOME_MESSAGE_UNIVERSAL
)
from src.data.task_bank import TaskBank
from src.data.algo_task_bank import AlgorithmicTaskBank, Difficulty, Category
from src.execution.code_executor import CodeExecutor, ExecutionStatus, ErrorAnalyzer
from src.execution.code_analyzer import CodeAnalyzer
from src.models.knowledge_tracing import KnowledgeTracker
from src.utils.session_logger import SessionLogger
from src.utils.error_handling import (
    validate_input,
    check_ollama_connection,
    safe_execute,
    FallbackResponses,
    handle_ui_error,
)
from src.config import settings

# UI Theme imports
from interface.themes import get_theme, claude_dark

# Optional imports for enhanced features
try:
    from src.memory.manager import MemoryManager
    from src.models.cognitive_load import CognitiveLoadEstimator
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    MemoryManager = None
    CognitiveLoadEstimator = None

# T033: Tool imports for display
try:
    from src.tools import tool_registry, ensure_tools_registered, ToolType
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False
    tool_registry = None

# Innovation imports (009-groundbreaking-innovations)
try:
    from src.models.task_synthesizer import TaskSynthesizer
    TASK_SYNTH_AVAILABLE = True
except ImportError:
    TASK_SYNTH_AVAILABLE = False
    TaskSynthesizer = None

try:
    from src.models.learning_path_optimizer import LearningPathOptimizer
    from src.data.knowledge_graph import SKILL_GRAPH, get_skill_name_ru
    LEARNING_PATH_AVAILABLE = True
except ImportError:
    LEARNING_PATH_AVAILABLE = False
    LearningPathOptimizer = None
    SKILL_GRAPH = {}
    get_skill_name_ru = lambda x: x

try:
    from src.models.vision_analyzer import VisionAnalyzer
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    VisionAnalyzer = None

try:
    from src.models.metacognitive_tracker import MetacognitiveTracker
    METACOGNITIVE_AVAILABLE = True
except ImportError:
    METACOGNITIVE_AVAILABLE = False
    MetacognitiveTracker = None


# Системный промпт для программирования
CODE_TUTOR_SYSTEM = """Ты — сократический репетитор по программированию и алгоритмам.

## ТВОЯ РОЛЬ:
Помогать студенту решить алгоритмическую задачу через наводящие вопросы.
НЕ давай готовый код! Направляй к решению.

## ФОРМАТИРОВАНИЕ:
- Код: ```python ... ```
- Сложность: $O(n)$, $O(n \\log n)$

## СТРАТЕГИИ:
1. Если не знает с чего начать → спроси про входные данные
2. Если ошибка → укажи на тип, но не исправляй
3. Если неоптимально → спроси про сложность
4. Если почти правильно → поддержи

ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ!"""


class MITSUnified:
    """Единое приложение MITS с поддержкой памяти и когнитивной нагрузки."""

    def __init__(self):
        self.llm_client: Optional[LLMClient] = None
        self.math_bank: Optional[TaskBank] = None
        self.algo_bank: Optional[AlgorithmicTaskBank] = None
        self.executor: Optional[CodeExecutor] = None
        self.analyzer: Optional[CodeAnalyzer] = None
        self.knowledge_tracker: Optional[KnowledgeTracker] = None
        self.logger: Optional[SessionLogger] = None

        # Enhanced features
        self.memory_manager: Optional['MemoryManager'] = None
        self.cognitive_estimator: Optional['CognitiveLoadEstimator'] = None
        self.session_id: Optional[str] = None

        self.is_initialized = False
        self.student_id = str(uuid.uuid4())[:8]

        # Текущие задачи
        self.current_math_task = None
        self.current_algo_task = None
        self.last_code_result = None

        # Cognitive load tracking
        self._last_response_time = None
        self._consecutive_errors = 0

        # Innovation components (009)
        self.task_synthesizer: Optional['TaskSynthesizer'] = None
        self.learning_path_optimizer: Optional['LearningPathOptimizer'] = None
        self.vision_analyzer: Optional['VisionAnalyzer'] = None
        self.metacognitive_tracker: Optional['MetacognitiveTracker'] = None
        self.current_learning_path = None
        self._session_start_time = None
    
    def initialize(self) -> str:
        """Инициализация системы."""
        try:
            # Check Ollama connection first
            if not check_ollama_connection():
                return "❌ Ollama не запущен. Выполните: `ollama serve`"

            self.llm_client = LLMClient()

            self.math_bank = TaskBank()
            self.algo_bank = AlgorithmicTaskBank()
            self.executor = CodeExecutor(timeout_seconds=5.0)
            self.analyzer = CodeAnalyzer()
            self.knowledge_tracker = KnowledgeTracker()
            self.logger = SessionLogger()

            # Initialize memory system if available
            memory_status = "❌ Недоступно"
            if MEMORY_AVAILABLE and MemoryManager:
                try:
                    self.memory_manager = MemoryManager()
                    self.session_id, _, _ = self.memory_manager.start_session(self.student_id)
                    memory_status = "✅ Активно"
                except Exception as e:
                    memory_status = f"⚠️ Ошибка: {str(e)[:30]}"

            # Initialize cognitive load estimator if available
            cognitive_status = "❌ Недоступно"
            if MEMORY_AVAILABLE and CognitiveLoadEstimator:
                try:
                    self.cognitive_estimator = CognitiveLoadEstimator()
                    cognitive_status = "✅ Активно"
                except Exception as e:
                    cognitive_status = f"⚠️ Ошибка: {str(e)[:30]}"

            # === Initialize Innovation Components (009) ===
            innovations_status = []

            # Task Synthesizer
            if TASK_SYNTH_AVAILABLE:
                try:
                    self.task_synthesizer = TaskSynthesizer()
                    innovations_status.append("🎲 Генератор задач: ✅")
                except Exception as e:
                    innovations_status.append(f"🎲 Генератор задач: ⚠️ {str(e)[:20]}")

            # Learning Path Optimizer
            if LEARNING_PATH_AVAILABLE:
                try:
                    self.learning_path_optimizer = LearningPathOptimizer()
                    innovations_status.append("🗺️ Путь обучения: ✅")
                except Exception as e:
                    innovations_status.append(f"🗺️ Путь обучения: ⚠️ {str(e)[:20]}")

            # Vision Analyzer (lazy load - heavy on VRAM)
            if VISION_AVAILABLE:
                innovations_status.append("📷 OCR решений: ✅ (по требованию)")

            # Metacognitive Tracker
            if METACOGNITIVE_AVAILABLE:
                try:
                    self.metacognitive_tracker = MetacognitiveTracker()
                    innovations_status.append("🧠 Метакогниция: ✅")
                except Exception as e:
                    innovations_status.append(f"🧠 Метакогниция: ⚠️ {str(e)[:20]}")

            # Track session start for reflection
            import datetime
            self._session_start_time = datetime.datetime.now()

            self.is_initialized = True

            math_count = len(self.math_bank.tasks)
            algo_stats = self.algo_bank.get_stats()

            # Get hardware config
            hw_config = self.llm_client.get_hardware_config()
            vram_info = self.llm_client.estimate_vram_usage()

            return f"""✅ **Система MITS готова!**

🤖 Модель: `{settings.MODEL_NAME}`
👤 ID студента: `{self.student_id}`
🔗 Сессия: `{self.session_id or 'N/A'}`

📚 **Банки задач:**
  • Математика: {math_count} задач
  • Алгоритмы: {algo_stats['total']} задач
    - 🟢 Easy: {algo_stats['by_difficulty']['easy']}
    - 🟡 Medium: {algo_stats['by_difficulty']['medium']}
    - 🔴 Hard: {algo_stats['by_difficulty']['hard']}

🧠 **Расширенные функции:**
  • Память: {memory_status}
  • Когнитивная нагрузка: {cognitive_status}

🚀 **Инновации (009):**
{chr(10).join('  • ' + s for s in innovations_status) if innovations_status else '  • Не активны'}

⚙️ **Оборудование:**
  • GPU слоёв: {hw_config['gpu_layers']}
  • Контекст: {hw_config['context_length']} токенов
  • VRAM: ~{vram_info['estimated_vram_gb']} GB
  • {vram_info['recommendation']}"""

        except Exception as e:
            return f"❌ Ошибка инициализации: {str(e)}"
    
    # ==================== СВОБОДНЫЙ ДИАЛОГ ====================

    def chat(self, message: str, history: List) -> Tuple[str, List]:
        """Свободный диалог с AI. Thinking встраивается в ответ."""
        if not self.is_initialized:
            return "", history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": "Система не инициализирована. Нажмите 'Запустить'."}
            ]

        try:
            cleaned_message = validate_input(message, allow_empty=False)
        except Exception:
            return "", history + [
                {"role": "user", "content": message or ""},
                {"role": "assistant", "content": FallbackResponses.get_fallback("empty_input", "ru")}
            ]

        import time
        start_time = time.time()

        try:
            chat_history = [
                {"role": m["role"], "content": self._extract_content(m["content"])}
                for m in history[-10:]
            ]

            messages = [{"role": "system", "content": UNIVERSAL_TUTOR_SYSTEM}]
            messages.extend(chat_history)
            messages.append({"role": "user", "content": cleaned_message})

            result = self.llm_client.chat_with_thinking(messages=messages)

            thinking = result.get('thinking', '')
            response = result.get('response', '')

            if not thinking:
                response = self._extract_message(result.get('raw', response))

            response_time_ms = (time.time() - start_time) * 1000
            self._last_response_time = response_time_ms

            # Format with inline thinking
            formatted_response = self._format_response_with_thinking(thinking, response, response_time_ms)

            if self.memory_manager and self.session_id:
                safe_execute(
                    self.memory_manager.record_interaction,
                    self.session_id,
                    cleaned_message,
                    response,
                    is_correct=None,
                    response_time_ms=response_time_ms
                )

            new_history = history + [
                {"role": "user", "content": cleaned_message},
                {"role": "assistant", "content": formatted_response}
            ]

            return "", new_history

        except Exception as e:
            error_msg = FallbackResponses.get_fallback("tutor", "ru")
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                error_msg = FallbackResponses.get_fallback("connection", "ru")

            return "", history + [
                {"role": "user", "content": cleaned_message},
                {"role": "assistant", "content": f"Ошибка: {error_msg}"}
            ]

    def chat_stream(self, message: str, history: List):
        """
        Streaming chat - yields tokens progressively for real-time UI.
        Thinking is embedded inline in the response (Claude-style).
        """
        if not self.is_initialized:
            yield (
                "",
                history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": "Система не инициализирована. Нажмите 'Запустить'."}
                ]
            )
            return

        # Validate input
        try:
            cleaned_message = validate_input(message, allow_empty=False)
        except Exception:
            yield (
                "",
                history + [
                    {"role": "user", "content": message or ""},
                    {"role": "assistant", "content": FallbackResponses.get_fallback("empty_input", "ru")}
                ]
            )
            return

        import time
        start_time = time.time()

        try:
            # Build messages for LLM
            chat_history = [
                {"role": m["role"], "content": self._extract_content(m["content"])}
                for m in history[-10:]
            ]

            messages = [{"role": "system", "content": UNIVERSAL_TUTOR_SYSTEM}]
            messages.extend(chat_history)
            messages.append({"role": "user", "content": cleaned_message})

            # Start with user message and thinking indicator
            new_history = history + [
                {"role": "user", "content": cleaned_message},
                {"role": "assistant", "content": "*Думаю...*"}
            ]

            yield ("", new_history)

            # Stream the response
            full_response = ""
            thinking_buffer = ""
            in_thinking = False

            for token in self.llm_client.chat_stream(messages=messages):
                full_response += token

                # Handle thinking tags
                if "<think>" in full_response and not in_thinking:
                    in_thinking = True
                    new_history[-1]["content"] = "*Размышляю...*"
                    yield ("", new_history)
                    continue

                if in_thinking:
                    if "</think>" in full_response:
                        in_thinking = False
                        idx_start = full_response.find("<think>") + 7
                        idx_end = full_response.find("</think>")
                        thinking_buffer = full_response[idx_start:idx_end]
                        response_part = full_response[idx_end + 8:].strip()
                        new_history[-1]["content"] = response_part if response_part else "*Формирую ответ...*"
                    else:
                        thinking_buffer = full_response[full_response.find("<think>") + 7:]
                else:
                    if "</think>" in full_response:
                        idx_end = full_response.find("</think>")
                        new_history[-1]["content"] = full_response[idx_end + 8:].strip()
                    else:
                        new_history[-1]["content"] = full_response

                yield ("", new_history)

            # Final yield with complete response
            response_time_ms = (time.time() - start_time) * 1000
            self._last_response_time = response_time_ms

            # Extract message if JSON
            final_response = new_history[-1]["content"]
            if not thinking_buffer:
                final_response = self._extract_message(full_response)

            # Format response with inline thinking (Claude-style)
            formatted_response = self._format_response_with_thinking(
                thinking_buffer, final_response, response_time_ms
            )
            new_history[-1]["content"] = formatted_response

            # Record in memory
            if self.memory_manager and self.session_id:
                safe_execute(
                    self.memory_manager.record_interaction,
                    self.session_id,
                    cleaned_message,
                    final_response,
                    is_correct=None,
                    response_time_ms=response_time_ms
                )

            yield ("", new_history)

        except Exception as e:
            error_msg = FallbackResponses.get_fallback("tutor", "ru")
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                error_msg = FallbackResponses.get_fallback("connection", "ru")

            yield (
                "",
                history + [
                    {"role": "user", "content": cleaned_message},
                    {"role": "assistant", "content": f"Ошибка: {error_msg}"}
                ]
            )

    def _extract_content(self, content):
        """Extract string content from Gradio 6.x message format."""
        if isinstance(content, str):
            return content
        if isinstance(content, list) and len(content) > 0:
            first_item = content[0]
            if isinstance(first_item, dict) and 'text' in first_item:
                return first_item['text']
        return str(content)

    def _format_thinking_display(self, thinking: str, response_time_ms: float) -> str:
        """Форматирование размышлений для отображения (legacy)."""
        if not thinking:
            return ""
        if len(thinking) > 2000:
            thinking = thinking[:2000] + "..."
        return thinking

    def _format_response_with_thinking(self, thinking: str, response: str, response_time_ms: float) -> str:
        """Форматирование ответа с встроенными размышлениями (как в Claude)."""
        if not thinking:
            return response

        # Truncate thinking if too long
        if len(thinking) > 1500:
            thinking = thinking[:1500] + "..."

        # Format thinking as collapsible block
        thinking_block = f"""<details>
<summary>💭 Размышления ({response_time_ms:.0f} мс)</summary>

{thinking}

</details>

"""
        return thinking_block + response

    def _extract_message(self, raw_response: str) -> str:
        """Extract message from JSON response or return raw text."""
        if not raw_response:
            return raw_response

        text = raw_response.strip()

        # Method 1: Direct JSON parse (strict=False for control chars)
        try:
            parsed = json.loads(text, strict=False)
            if isinstance(parsed, dict) and "message" in parsed:
                return parsed["message"]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # Method 2: Manual string extraction for "message": "..."
        # Find "message" key position
        msg_key = '"message"'
        key_pos = text.find(msg_key)
        if key_pos != -1:
            # Find the colon after the key
            colon_pos = text.find(':', key_pos + len(msg_key))
            if colon_pos != -1:
                # Find opening quote
                quote_start = text.find('"', colon_pos + 1)
                if quote_start != -1:
                    # Find closing quote (handle escaped quotes)
                    pos = quote_start + 1
                    while pos < len(text):
                        if text[pos] == '"' and text[pos-1] != '\\':
                            # Found end quote
                            message = text[quote_start + 1:pos]
                            # Unescape
                            message = message.replace('\\"', '"')
                            message = message.replace('\\n', '\n')
                            return message
                        pos += 1

        return raw_response

    # ==================== T033: ИНСТРУМЕНТЫ ====================

    def get_tools_info(self) -> str:
        """
        Получить информацию о доступных инструментах.

        Returns:
            Форматированная строка с описанием инструментов
        """
        if not TOOLS_AVAILABLE or not tool_registry:
            return "❌ Инструменты недоступны"

        try:
            ensure_tools_registered()
            tools = tool_registry.get_all()

            if not tools:
                return "⚠️ Нет зарегистрированных инструментов"

            lines = ["### 🛠️ Доступные инструменты\n"]

            tool_icons = {
                "calculator": "🧮",
                "web_search": "🔍",
                "knowledge_search": "📚"
            }

            for name, tool in tools.items():
                icon = tool_icons.get(name, "🔧")
                lines.append(f"**{icon} {name}**")
                lines.append(f"> {tool.description}\n")

            lines.append("---")
            lines.append("*Инструменты используются автоматически при необходимости*")

            return "\n".join(lines)

        except Exception as e:
            return f"❌ Ошибка загрузки инструментов: {str(e)[:50]}"

    # ==================== МАТЕМАТИКА ====================
    
    def get_math_task(self, topic: str, difficulty: str) -> Tuple[str, str]:
        """Получить математическую задачу."""
        if not self.is_initialized:
            return "⚠️ Система не инициализирована", ""
        
        topic_map = {
            "adaptive": None,
            "any": None,
            "derivatives": "derivatives",
            "integrals": "integrals",
            "limits": "limits",
            "equations": "equations",
        }
        
        t = topic_map.get(topic)
        d = difficulty if difficulty != "any" else None
        
        if topic == "adaptive":
            # Адаптивный выбор на основе знаний
            student = self.knowledge_tracker.get_student(self.student_id)
            # Get skill masteries from student model
            skill_masteries = {name: skill.mastery for name, skill in student.skills.items()}
            task = self.math_bank.get_adaptive_task(skill_masteries)
        else:
            task = self.math_bank.get_task(topic=t, difficulty=d)
        
        if not task:
            return "Задачи не найдены", ""

        self.current_math_task = task

        # Task is a Pydantic model - access attributes directly
        topic_name = getattr(task, 'topic', 'Математика')
        difficulty_name = getattr(task, 'difficulty', 'medium')
        skills_list = getattr(task, 'skills', [])
        problem_text = getattr(task, 'problem', '')

        info = f"**Тема:** {topic_name} | **Сложность:** {difficulty_name}"
        if skills_list:
            info += f" | **Навыки:** {', '.join(skills_list)}"

        return problem_text, info
    
    def check_math_answer(self, answer: str, history: List) -> Tuple[str, List]:
        """Проверить математический ответ с помощью LLM (сократический метод)."""
        if not self.current_math_task:
            return "", history + [
                {"role": "user", "content": answer},
                {"role": "assistant", "content": "Сначала выберите задачу"}
            ]

        problem = getattr(self.current_math_task, 'problem', '')
        correct_answer = getattr(self.current_math_task, 'answer', '')
        solution = getattr(self.current_math_task, 'solution', '')
        hints = getattr(self.current_math_task, 'hints', [])
        skills = getattr(self.current_math_task, 'skills', [])

        # Build context for LLM
        system_prompt = f"""Ты — сократический репетитор по математике. Студент решает задачу.

ЗАДАЧА: {problem}

ПРАВИЛЬНЫЙ ОТВЕТ: {correct_answer}

РЕШЕНИЕ: {solution}

ПОДСКАЗКИ: {'; '.join(hints) if hints else 'нет'}

ПРАВИЛА:
1. Проверь ответ студента. Он может быть записан в другой форме, но быть верным.
2. Если ответ ВЕРНЫЙ — похвали кратко и подтверди.
3. Если ответ НЕВЕРНЫЙ или ЧАСТИЧНО верный:
   - НЕ давай правильный ответ напрямую
   - Задай наводящий вопрос о том, где ошибка
   - Направь к правильному решению
4. Отвечай кратко, 2-3 предложения максимум.
5. Используй LaTeX для формул: $x^2$, $$\\frac{{a}}{{b}}$$"""

        # Build conversation for LLM
        messages = [{"role": "system", "content": system_prompt}]

        # Add relevant history (last few exchanges about this problem)
        for msg in history[-6:]:
            messages.append({
                "role": msg["role"],
                "content": self._extract_content(msg["content"])
            })

        messages.append({"role": "user", "content": answer})

        try:
            # Use LLM to check and respond
            result = self.llm_client.chat_with_thinking(messages=messages)
            response = result.get('response', '')

            if not response:
                response = self._extract_message(result.get('raw', ''))

            # Determine if correct (simple heuristic + LLM response)
            is_correct = any(word in response.lower() for word in
                           ['правильно', 'верно', 'молодец', 'отлично', 'верный', 'правильный'])

            self.knowledge_tracker.record_attempt(self.student_id, skills, is_correct=is_correct)

        except Exception as e:
            response = f"Ошибка проверки: {str(e)[:50]}"

        return "", history + [
            {"role": "user", "content": answer},
            {"role": "assistant", "content": response}
        ]
    
    def get_math_hint(self) -> str:
        """Подсказка для математической задачи."""
        if not self.current_math_task:
            return "Сначала выберите задачу"

        hints = getattr(self.current_math_task, 'hints', [])
        if hints:
            return f"**Подсказка:**\n\n{hints[0]}"
        return "Подсказок для этой задачи нет"

    def show_math_solution(self) -> str:
        """Показать решение математической задачи."""
        if not self.current_math_task:
            return "Сначала выберите задачу"

        solution = getattr(self.current_math_task, 'solution', '')
        answer = getattr(self.current_math_task, 'answer', '')
        skills = getattr(self.current_math_task, 'skills', [])

        self.knowledge_tracker.record_attempt(self.student_id, skills, is_correct=False)

        return f"## Решение\n\n{solution}\n\n**Ответ:** {answer}"
    
    # ==================== ПРОГРАММИРОВАНИЕ ====================
    
    def get_algo_task(self, task_id: str = "", difficulty: str = "easy", category: str = "any") -> Tuple[str, str, str]:
        """Получить алгоритмическую задачу."""
        if not self.is_initialized:
            return "⚠️ Система не инициализирована", "", ""
        
        if task_id:
            task = self.algo_bank.get_task(task_id)
        else:
            diff = Difficulty(difficulty) if difficulty != "any" else None
            cat = Category(category) if category != "any" else None
            task = self.algo_bank.get_random_task(difficulty=diff, category=cat)
        
        if not task:
            return "❌ Задача не найдена", "", ""
        
        self.current_algo_task = task
        
        template = f'''# {task.title_ru}
# Сложность: {task._diff_ru()}

# Ваше решение:

'''
        
        info = f"📋 **ID:** `{task.id}` | **Сложность:** {task._diff_emoji()} | **Тесты:** {len(task.test_cases)}"
        
        return task.get_problem_text(), template, info
    
    def run_code(self, code: str) -> str:
        """Запустить код на примерах."""
        if not self.current_algo_task:
            return "⚠️ Сначала выберите задачу"
        
        if not code.strip():
            return "⚠️ Введите код"
        
        # Берём видимые тесты
        from src.execution.code_executor import TestCase
        visible_tests = [
            TestCase(ex["input"], ex["output"])
            for ex in self.current_algo_task.examples[:3]
        ]
        
        result = self.executor.run_tests(code, visible_tests, stop_on_first_fail=True)
        self.last_code_result = result
        
        output = f"## 🧪 Результаты\n\n**Пройдено:** {result.passed}/{result.total}\n\n"
        
        for i, res in enumerate(result.results, 1):
            if res.is_correct:
                output += f"✅ Тест {i}: OK ({res.execution_time_ms:.0f} мс)\n"
            else:
                output += f"❌ Тест {i}: {res.status.value}\n"
                
                if res.status == ExecutionStatus.WRONG_ANSWER:
                    output += f"   Ожидалось: `{res.expected[:40]}`\n"
                    output += f"   Получено: `{res.output[:40]}`\n"
                elif res.status == ExecutionStatus.RUNTIME_ERROR:
                    analysis = ErrorAnalyzer.analyze(res.error)
                    output += f"   **{analysis['type']}**\n"
                    output += f"   💡 {analysis['hint']}\n"
                
                break
        
        return output
    
    def submit_code(self, code: str) -> str:
        """Отправить код на полную проверку."""
        if not self.current_algo_task:
            return "⚠️ Сначала выберите задачу"
        
        if not code.strip():
            return "⚠️ Введите код"
        
        result = self.executor.run_tests(code, self.current_algo_task.test_cases)
        self.last_code_result = result
        
        self.algo_bank.record_attempt(self.current_algo_task.id, result.is_accepted)
        
        if result.is_accepted:
            return f"""## 🎉 ACCEPTED!

**Все тесты пройдены!** ✅ {result.passed}/{result.total}

Отличная работа! Задача **{self.current_algo_task.title_ru}** решена!
"""
        else:
            output = f"## ❌ Неверный ответ\n\n**Пройдено:** {result.passed}/{result.total}\n\n"
            
            if result.first_failed:
                if result.first_failed.test_number > len(self.current_algo_task.examples):
                    output += "Ошибка на скрытом тесте. Проверьте граничные случаи.\n"
            
            return output
    
    def analyze_code(self, code: str) -> str:
        """Анализ кода."""
        if not code.strip():
            return "⚠️ Введите код"
        
        analysis = self.analyzer.analyze(code)
        
        output = f"## 📊 Анализ кода\n\n{analysis['summary']}\n\n"
        
        if analysis["issues"]:
            output += "### 🔍 Проблемы:\n\n"
            output += self.analyzer.get_formatted_issues()
        
        return output
    
    def get_algo_hint(self) -> str:
        """Подсказка для алгоритмической задачи."""
        if not self.current_algo_task:
            return "⚠️ Сначала выберите задачу"
        
        hints = self.current_algo_task.hints
        return f"💡 **Подсказка:**\n\n{hints[0]}" if hints else "💡 Подсказок нет"
    
    def show_algo_solution(self) -> Tuple[str, str]:
        """Показать решение."""
        if not self.current_algo_task:
            return "⚠️ Выберите задачу", ""
        
        return self.current_algo_task.solution_explanation or "Решение", self.current_algo_task.solution_code
    
    # ==================== ПРОФИЛЬ ====================

    def get_profile(self) -> str:
        """Профиль знаний студента."""
        if not self.is_initialized:
            return "⚠️ Система не инициализирована"

        student = self.knowledge_tracker.get_student(self.student_id)
        return student.get_summary()

    def get_analytics(self) -> str:
        """Аналитика сессий."""
        if not self.logger:
            return "⚠️ Система не инициализирована"

        analytics = self.logger.get_analytics()

        output = "## 📊 Аналитика обучения\n\n"
        output += f"- **Всего сессий:** {analytics.get('total_sessions', 0)}\n"
        output += f"- **Success@10:** {analytics.get('success_at_10', 0):.1%}\n"
        output += f"- **Telling@10:** {analytics.get('telling_at_10', 0):.1%}\n"
        output += f"- **Среднее время:** {analytics.get('avg_duration_seconds', 0):.0f} сек\n"

        return output

    # ==================== КОГНИТИВНАЯ НАГРУЗКА ====================

    def get_cognitive_load(self) -> str:
        """Получить текущую оценку когнитивной нагрузки."""
        if not self.is_initialized:
            return "⚠️ Система не инициализирована"

        output = "## 🧠 Когнитивная нагрузка\n\n"

        # Basic metrics
        if self._last_response_time:
            rt_indicator = "🟢" if self._last_response_time < 2000 else "🟡" if self._last_response_time < 5000 else "🔴"
            output += f"**Время последнего ответа:** {rt_indicator} {self._last_response_time:.0f} мс\n\n"

        error_indicator = "🟢" if self._consecutive_errors == 0 else "🟡" if self._consecutive_errors < 3 else "🔴"
        output += f"**Последовательные ошибки:** {error_indicator} {self._consecutive_errors}\n\n"

        # Advanced estimator if available
        if self.cognitive_estimator and self.memory_manager and self.session_id:
            try:
                context = self.memory_manager.get_full_context(self.session_id)
                if context and hasattr(context, 'session'):
                    session_data = context.session

                    # Estimate cognitive load
                    load_data = self.cognitive_estimator.estimate(
                        response_times=getattr(session_data, 'response_times', []),
                        error_rate=getattr(session_data, 'error_count', 0) /
                                  max(getattr(session_data, 'interaction_count', 1), 1),
                        task_complexity=0.5,  # Medium default
                        session_duration_minutes=getattr(session_data, 'duration_minutes', 0)
                    )

                    load_level = load_data.get('overall_load', 0.5)
                    load_bar = self._make_progress_bar(load_level)

                    output += f"### Общая нагрузка\n{load_bar} {load_level:.0%}\n\n"

                    # Components
                    if 'components' in load_data:
                        output += "### Компоненты:\n"
                        for name, value in load_data['components'].items():
                            output += f"- {name}: {value:.0%}\n"

                    # Recommendation
                    if load_level > 0.8:
                        output += "\n⚠️ **Рекомендация:** Высокая когнитивная нагрузка. Рекомендуется сделать перерыв.\n"
                    elif load_level > 0.6:
                        output += "\n💡 **Рекомендация:** Умеренная нагрузка. Попробуйте более простые задачи.\n"
                    else:
                        output += "\n✅ **Статус:** Нагрузка в норме. Продолжайте обучение!\n"

            except Exception as e:
                output += f"\n*Расширенная аналитика недоступна: {str(e)[:50]}*\n"
        else:
            output += "*Расширенный анализ недоступен. Включите модуль памяти.*\n"

        return output

    def _make_progress_bar(self, value: float, width: int = 20) -> str:
        """Create a text progress bar."""
        filled = int(value * width)
        empty = width - filled

        if value < 0.4:
            fill_char = "🟩"
        elif value < 0.7:
            fill_char = "🟨"
        else:
            fill_char = "🟥"

        return fill_char * filled + "⬜" * empty

    # ==================== ПАМЯТЬ ====================

    def get_memory_status(self) -> str:
        """Получить статус системы памяти."""
        if not self.is_initialized:
            return "⚠️ Система не инициализирована"

        output = "## 💾 Система памяти\n\n"

        if not self.memory_manager:
            output += "❌ **Память не активна**\n\n"
            output += "*Модуль памяти не загружен. Проверьте зависимости.*\n"
            return output

        output += f"✅ **Память активна**\n\n"
        output += f"- **ID студента:** `{self.student_id}`\n"
        output += f"- **ID сессии:** `{self.session_id}`\n\n"

        # Get session memory info
        try:
            context = self.memory_manager.get_full_context(self.session_id)
            if context:
                # Session info
                if hasattr(context, 'session') and context.session:
                    session = context.session
                    output += "### 📝 Текущая сессия\n"
                    output += f"- Взаимодействий: {getattr(session, 'interaction_count', 0)}\n"
                    output += f"- Правильных ответов: {getattr(session, 'correct_count', 0)}\n"
                    output += f"- Длительность: {getattr(session, 'duration_minutes', 0):.1f} мин\n\n"

                # Knowledge state
                if hasattr(context, 'knowledge_state') and context.knowledge_state:
                    ks = context.knowledge_state
                    output += "### 📊 Состояние знаний\n"

                    if hasattr(ks, 'topic_masteries'):
                        for topic, mastery in list(ks.topic_masteries.items())[:5]:
                            mastery_bar = self._make_progress_bar(mastery, 10)
                            output += f"- {topic}: {mastery_bar} {mastery:.0%}\n"

                    output += "\n"

                # Preferences
                if hasattr(context, 'preferences') and context.preferences:
                    output += "### ⚙️ Предпочтения\n"
                    for key, value in list(context.preferences.items())[:5]:
                        output += f"- {key}: {value}\n"

        except Exception as e:
            output += f"\n*Ошибка получения контекста: {str(e)[:50]}*\n"

        return output

    def clear_session_memory(self) -> str:
        """Очистить память текущей сессии."""
        if not self.memory_manager or not self.session_id:
            return "⚠️ Память не активна"

        try:
            # Start a new session
            self.session_id, _, _ = self.memory_manager.start_session(self.student_id)
            self._consecutive_errors = 0
            self._last_response_time = None
            return f"✅ Сессия сброшена. Новый ID: `{self.session_id}`"
        except Exception as e:
            return f"❌ Ошибка сброса: {str(e)}"

    # ==================== T041: СТАТИСТИКА КЭША ====================

    def get_cache_stats(self) -> str:
        """Получить статистику кэширования."""
        if not self.is_initialized:
            return "⚠️ Система не инициализирована"

        output = "## 📊 Статистика кэширования\n\n"

        try:
            from src.inference import get_cache_manager, get_rag_cache, get_hint_prefetcher

            # Response Cache
            cache_manager = get_cache_manager()
            response_stats = cache_manager.response_cache.stats

            output += "### 💬 Кэш ответов\n"
            output += f"- **Размер:** {response_stats['size']} / {response_stats['max_size']}\n"
            output += f"- **Попадания:** {response_stats['hits']}\n"
            output += f"- **Промахи:** {response_stats['misses']}\n"
            output += f"- **Hit Rate:** {response_stats['hit_rate']:.1%}\n"
            output += f"- **Семантический поиск:** {'✅' if response_stats['semantic_enabled'] else '❌'}\n"
            if response_stats['semantic_enabled']:
                output += f"- **Эмбеддингов:** {response_stats['embeddings_count']}\n"
            output += "\n"

            # RAG Cache
            try:
                rag_cache = get_rag_cache()
                rag_stats = rag_cache.stats

                output += "### 🔍 RAG кэш\n"
                output += f"- **Эмбеддинги:** {rag_stats['embedding_cache_size']}\n"
                output += f"- **Retrieval:** {rag_stats['retrieval_cache_size']}\n"
                output += f"- **TTL эмбеддингов:** {rag_stats['embedding_ttl']} сек\n"
                output += "\n"
            except Exception:
                output += "### 🔍 RAG кэш\n*Не инициализирован*\n\n"

            # Hint Prefetcher
            try:
                prefetcher = get_hint_prefetcher()
                prefetch_stats = prefetcher.stats

                output += "### 💡 Prefetcher подсказок\n"
                output += f"- **Кэш:** {prefetch_stats['cache_size']} / {prefetch_stats['max_cache_size']}\n"
                output += f"- **Попадания:** {prefetch_stats['hits']}\n"
                output += f"- **Hit Rate:** {prefetch_stats['hit_rate']:.1%}\n"
                output += f"- **Предзагружено:** {prefetch_stats['total_prefetched']}\n"
                output += f"- **Workers:** {prefetch_stats['workers_running']}\n"
            except Exception:
                output += "### 💡 Prefetcher подсказок\n*Не инициализирован*\n"

        except ImportError:
            output += "*Модуль кэширования недоступен*\n"
        except Exception as e:
            output += f"*Ошибка: {str(e)[:100]}*\n"

        return output

    # ==================== ИННОВАЦИИ (009) ====================

    def generate_new_task(self, topic: str, difficulty: str) -> Tuple[str, str]:
        """
        Генерация новой задачи с SymPy-верификацией.
        T032, T033: Task Synthesis UI
        """
        if not self.is_initialized:
            return "⚠️ Система не инициализирована", ""

        if not self.task_synthesizer:
            return "❌ Генератор задач не инициализирован", ""

        try:
            # Map difficulty
            diff_map = {"easy": "easy", "medium": "medium", "hard": "hard"}
            diff = diff_map.get(difficulty, "medium")

            task = self.task_synthesizer.generate_task(topic=topic, difficulty=diff)

            # Format output
            problem_text = f"""## 🎲 Сгенерированная задача

**Тема:** {task.topic}
**Сложность:** {task.difficulty.value if hasattr(task.difficulty, 'value') else task.difficulty}

### Условие:
{task.problem}

---
*Задача сгенерирована с SymPy-верификацией: {'✅' if task.sympy_verified else '⚠️'}*
"""

            info_text = f"""**ID:** `{task.id}`
**Верификация:** {'✅ SymPy' if task.sympy_verified else '⚠️ Не верифицирована'}
**Ответ (скрыт):** ||{task.answer}||
"""
            self.current_math_task = task
            return problem_text, info_text

        except Exception as e:
            return f"❌ Ошибка генерации: {str(e)}", ""

    def get_learning_path(self, target_skill: str) -> str:
        """
        Построение индивидуального пути обучения.
        T062, T063, T064: Learning Path UI
        """
        if not self.is_initialized:
            return "⚠️ Система не инициализирована"

        if not self.learning_path_optimizer:
            return "❌ Оптимизатор пути не инициализирован"

        try:
            # Get student mastery from knowledge tracker
            student_mastery = {}
            if self.knowledge_tracker:
                student_mastery = self.knowledge_tracker.get_all_masteries()

            # Create path
            path = self.learning_path_optimizer.create_path(
                target_skill=target_skill,
                student_mastery=student_mastery,
                student_id=self.student_id
            )

            self.current_learning_path = path

            # Visualize
            visualization = self.learning_path_optimizer.visualize_path(path, format="ascii")

            output = f"""## 🗺️ Путь обучения

**Цель:** {path.target_skill_name_ru}
**Статус:** {path.status.value if hasattr(path.status, 'value') else path.status}
**Навыков в пути:** {len(path.skills)}
**Оценка времени:** ~{path.estimated_hours:.1f} часов

---

{visualization}

---

### Рекомендации
"""
            # Get recommendations
            recs = self.learning_path_optimizer.get_skill_recommendations(student_mastery, count=3)
            for rec in recs:
                output += f"- **{rec['skill_name_ru']}**: {rec['rationale']}\n"

            return output

        except Exception as e:
            return f"❌ Ошибка построения пути: {str(e)}"

    def analyze_handwritten_solution(self, image, problem_text: str) -> str:
        """
        Анализ рукописного решения через Vision Model.
        T073, T074: Vision Analysis UI
        """
        if not self.is_initialized:
            return "⚠️ Система не инициализирована"

        if not VISION_AVAILABLE:
            return "❌ Модуль Vision не установлен"

        try:
            # Lazy init vision analyzer
            if not self.vision_analyzer:
                self.vision_analyzer = VisionAnalyzer()

            # Check if model available
            if not self.vision_analyzer.is_available():
                return "❌ Vision модель не установлена. Выполните: `ollama pull minicpm-v`"

            # Get expected answer from current task
            expected_answer = None
            if self.current_math_task:
                expected_answer = str(self.current_math_task.answer)

            # Analyze (sync version)
            result = self.vision_analyzer.analyze_image_sync(
                image_path=image,
                problem=problem_text,
                expected_answer=expected_answer,
                student_id=self.student_id,
            )

            return result.feedback

        except Exception as e:
            return f"❌ Ошибка анализа: {str(e)}"

    def get_session_reflection(self) -> str:
        """
        Получить рефлексию после сессии.
        T052: End-of-session reflection
        """
        if not self.is_initialized:
            return "⚠️ Система не инициализирована"

        if not self.metacognitive_tracker:
            return "❌ Метакогнитивный трекер не инициализирован"

        try:
            import datetime

            # Calculate session duration
            duration_minutes = 0
            if self._session_start_time:
                delta = datetime.datetime.now() - self._session_start_time
                duration_minutes = delta.total_seconds() / 60

            # Get session stats
            tasks_attempted = 0
            tasks_correct = 0
            topics = []

            if self.memory_manager and self.session_id:
                context = self.memory_manager.get_full_context(self.session_id)
                if context and hasattr(context, 'session'):
                    tasks_attempted = getattr(context.session, 'interaction_count', 0)
                    tasks_correct = getattr(context.session, 'correct_count', 0)

            # Generate reflection
            reflection = self.metacognitive_tracker.get_reflection_prompt(
                session_duration_minutes=duration_minutes,
                tasks_attempted=tasks_attempted,
                tasks_correct=tasks_correct,
                topics_covered=topics
            )

            # Get metacognitive profile
            profile = self.metacognitive_tracker.update_profile()
            profile_info = f"""
---

### Метакогнитивный профиль

| Аспект | Уровень |
|--------|---------|
| Общий | {profile.overall_level.value} |
| Осознанность | {profile.awareness_level.value} |
| Регуляция | {profile.regulation_level.value} |
| Оценка | {profile.evaluation_level.value} |

*Моментов затруднений: {profile.stuck_points_count}*
*Успешных восстановлений: {profile.successful_recoveries}*
"""

            return reflection + profile_info

        except Exception as e:
            return f"❌ Ошибка генерации рефлексии: {str(e)}"

    def get_skill_choices(self) -> List[Tuple[str, str]]:
        """Get skill choices for dropdown."""
        if not LEARNING_PATH_AVAILABLE or not SKILL_GRAPH:
            return [("Не доступно", "none")]

        choices = []
        for skill_id in SKILL_GRAPH.keys():
            name_ru = get_skill_name_ru(skill_id)
            choices.append((name_ru, skill_id))

        # Sort by Russian name
        choices.sort(key=lambda x: x[0])
        return choices


# Создаём приложение
app = MITSUnified()


def _load_css() -> str:
    """Load custom CSS from file."""
    css_path = Path(__file__).parent / "styles" / "claude.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return ""


def _load_js() -> str:
    """Load custom JavaScript from file."""
    js_path = Path(__file__).parent / "styles" / "claude.js"
    if js_path.exists():
        return js_path.read_text(encoding="utf-8")
    return ""


def _get_avatar_paths() -> tuple:
    """Get avatar paths for chatbot."""
    base_path = Path(__file__).parent / "assets"
    user_avatar = base_path / "user_avatar.svg"
    bot_avatar = base_path / "bot_avatar.svg"

    # Return paths if they exist, otherwise None
    return (
        str(user_avatar) if user_avatar.exists() else None,
        str(bot_avatar) if bot_avatar.exists() else None
    )


def create_interface() -> gr.Blocks:
    """Создать интерфейс в стиле Claude."""

    # Load theme based on settings
    theme = get_theme(settings.UI_DEFAULT_THEME)
    custom_css = _load_css()
    custom_js = _load_js()
    avatar_images = _get_avatar_paths()

    # Create Blocks and apply theme, CSS, JS (Gradio 6.x style)
    interface = gr.Blocks(title="MITS")
    interface.theme = theme
    interface.css = custom_css
    interface.js = custom_js

    with interface:

        # Minimal header
        with gr.Row():
            with gr.Column(scale=6):
                gr.Markdown("# MITS")
            with gr.Column(scale=1):
                init_btn = gr.Button("Запустить", variant="primary", size="sm")

        status = gr.Textbox(
            value="Нажмите 'Запустить'",
            show_label=False,
            interactive=False,
            elem_classes=["status-bar"]
        )

        with gr.Tabs():

            # ===== Вкладка: Диалог =====
            with gr.Tab("Диалог"):
                chat_box = gr.Chatbot(
                    value=[{"role": "assistant", "content": "Привет! Я MITS — твой репетитор по математике и программированию. Задавай вопросы."}],
                    height=550,
                    avatar_images=avatar_images,
                    latex_delimiters=[
                        {"left": "$$", "right": "$$", "display": True},
                        {"left": "$", "right": "$", "display": False},
                    ],
                    elem_classes=["chat-container"],
                    sanitize_html=False  # Allow <details> for inline thinking
                )

                with gr.Row(elem_classes=["input-container"]):
                    chat_input = gr.Textbox(
                        placeholder="Напишите сообщение...",
                        show_label=False,
                        scale=6,
                        lines=1
                    )
                    chat_btn = gr.Button("Отправить", variant="primary", scale=1)
            
            # ===== Вкладка: Математика =====
            with gr.Tab("📐 Математика"):
                with gr.Row():
                    with gr.Column(scale=1):
                        math_topic = gr.Dropdown(
                            label="Тема",
                            choices=[
                                ("🎯 Адаптивный выбор", "adaptive"),
                                ("Любая", "any"),
                                ("Производные", "derivatives"),
                                ("Интегралы", "integrals"),
                                ("Пределы", "limits"),
                                ("Уравнения", "equations"),
                            ],
                            value="adaptive"
                        )
                        math_diff = gr.Dropdown(
                            label="Сложность",
                            choices=[("Любая", "any"), ("Лёгкий", "easy"), ("Средний", "medium"), ("Сложный", "hard")],
                            value="any"
                        )
                        math_get_btn = gr.Button("📋 Получить задачу", variant="primary")
                        
                        math_info = gr.Markdown()
                        
                        with gr.Row():
                            math_hint_btn = gr.Button("💡 Подсказка", size="sm")
                            math_sol_btn = gr.Button("📖 Решение", size="sm")
                        
                        math_hint_out = gr.Markdown()
                    
                    with gr.Column(scale=2):
                        math_problem = gr.Markdown(
                            value="*Выберите задачу*",
                            latex_delimiters=[
                                {"left": "$$", "right": "$$", "display": True},
                                {"left": "$", "right": "$", "display": False},
                            ]
                        )
                        
                        math_chat = gr.Chatbot(
                            value=[],
                            height=300,
                            avatar_images=avatar_images,
                            latex_delimiters=[
                                {"left": "$$", "right": "$$", "display": True},
                                {"left": "$", "right": "$", "display": False},
                            ],
                            elem_classes=["chat-container"],
                            sanitize_html=False  # Allow <details> for inline thinking
                        )
                        
                        with gr.Row():
                            math_answer = gr.Textbox(placeholder="Ваш ответ...", show_label=False, scale=5)
                            math_check_btn = gr.Button("✓", variant="primary", scale=1)
            
            # ===== Вкладка: Программирование =====
            with gr.Tab("💻 Алгоритмы"):
                with gr.Row():
                    with gr.Column(scale=1):
                        algo_diff = gr.Dropdown(
                            label="Сложность",
                            choices=[("🟢 Easy", "easy"), ("🟡 Medium", "medium"), ("🔴 Hard", "hard")],
                            value="easy"
                        )
                        algo_cat = gr.Dropdown(
                            label="Категория",
                            choices=[
                                ("Любая", "any"),
                                ("Массивы", "arrays"),
                                ("Строки", "strings"),
                                ("Математика", "math"),
                                ("Поиск", "searching"),
                                ("Сортировка", "sorting"),
                                ("ДП", "dynamic_programming"),
                            ],
                            value="any"
                        )
                        algo_get_btn = gr.Button("🎲 Случайная задача", variant="primary")
                        
                        algo_id = gr.Textbox(label="Или ID задачи", placeholder="two_sum")
                        algo_load_btn = gr.Button("📥 Загрузить")
                        
                        algo_info = gr.Markdown()
                        
                        with gr.Row():
                            algo_hint_btn = gr.Button("💡", size="sm")
                            algo_sol_btn = gr.Button("📖", size="sm")
                        
                        algo_hint_out = gr.Markdown()
                    
                    with gr.Column(scale=2):
                        algo_problem = gr.Markdown(value="*Выберите задачу*")
                        
                        algo_code = gr.Code(language="python", label="Код", lines=15)
                        
                        with gr.Row():
                            algo_run_btn = gr.Button("▶️ Тест", scale=1)
                            algo_analyze_btn = gr.Button("📊 Анализ", scale=1)
                            algo_submit_btn = gr.Button("📤 Отправить", variant="primary", scale=1)
                        
                        algo_results = gr.Markdown(value="*Результаты*")
                        
                        algo_solution = gr.Code(language="python", label="Решение", visible=False)
            
            # ===== Вкладка: Профиль =====
            with gr.Tab("📊 Профиль"):
                with gr.Row():
                    profile_btn = gr.Button("🔄 Обновить профиль")
                    analytics_btn = gr.Button("📈 Аналитика")

                profile_out = gr.Markdown(value="*Нажмите 'Обновить профиль'*")

            # ===== Вкладка: Когнитивная нагрузка =====
            with gr.Tab("🧠 Нагрузка"):
                gr.Markdown("*Мониторинг когнитивной нагрузки в реальном времени*")

                cognitive_btn = gr.Button("🔄 Обновить")
                cognitive_out = gr.Markdown(value="*Нажмите 'Обновить' для анализа*")

                gr.Markdown("""
---
**Индикаторы:**
- 🟢 Низкая нагрузка — можно продолжать
- 🟡 Умеренная нагрузка — будьте внимательны
- 🔴 Высокая нагрузка — рекомендуется перерыв
                """)

            # ===== Вкладка: Память =====
            with gr.Tab("💾 Память"):
                gr.Markdown("*Система dual-memory: сессия + долгосрочная память*")

                with gr.Row():
                    memory_btn = gr.Button("🔄 Статус памяти")
                    cache_stats_btn = gr.Button("📊 Статистика кэша")
                    clear_memory_btn = gr.Button("🗑️ Новая сессия", variant="stop")

                memory_out = gr.Markdown(value="*Нажмите 'Статус памяти' для просмотра*")

            # ===== Вкладка: Генератор задач (Innovation 009) =====
            with gr.Tab("🎲 Генератор"):
                gr.Markdown("*Генерация бесконечных задач с SymPy-верификацией*")

                with gr.Row():
                    with gr.Column(scale=1):
                        gen_topic = gr.Dropdown(
                            label="Тема",
                            choices=[
                                ("Производные", "derivatives"),
                                ("Интегралы", "integrals"),
                                ("Пределы", "limits"),
                                ("Уравнения", "equations"),
                                ("Тригонометрия", "trigonometry"),
                            ],
                            value="derivatives"
                        )
                        gen_diff = gr.Dropdown(
                            label="Сложность",
                            choices=[("Лёгкий", "easy"), ("Средний", "medium"), ("Сложный", "hard")],
                            value="medium"
                        )
                        gen_btn = gr.Button("🎲 Сгенерировать", variant="primary")

                        gen_info = gr.Markdown()

                    with gr.Column(scale=2):
                        gen_problem = gr.Markdown(
                            value="*Нажмите 'Сгенерировать' для создания задачи*",
                            latex_delimiters=[
                                {"left": "$$", "right": "$$", "display": True},
                                {"left": "$", "right": "$", "display": False},
                            ]
                        )

            # ===== Вкладка: Путь обучения (Innovation 009) =====
            with gr.Tab("🗺️ Путь"):
                gr.Markdown("*Персонализированный путь обучения на основе графа знаний*")

                with gr.Row():
                    path_skill = gr.Dropdown(
                        label="Целевой навык",
                        choices=app.get_skill_choices(),
                        value="integration_basic" if LEARNING_PATH_AVAILABLE else "none"
                    )
                    path_btn = gr.Button("🗺️ Построить путь", variant="primary")

                path_out = gr.Markdown(value="*Выберите целевой навык и нажмите 'Построить путь'*")

            # ===== Вкладка: OCR решений (Innovation 009) =====
            with gr.Tab("📷 OCR"):
                gr.Markdown("*Анализ рукописных математических решений*")

                with gr.Row():
                    with gr.Column(scale=1):
                        ocr_image = gr.Image(
                            label="Загрузите фото решения",
                            type="filepath"
                        )
                        ocr_problem = gr.Textbox(
                            label="Условие задачи (опционально)",
                            placeholder="Найти производную f(x) = x²sin(x)",
                            lines=2
                        )
                        ocr_btn = gr.Button("📷 Анализировать", variant="primary")

                    with gr.Column(scale=2):
                        ocr_result = gr.Markdown(value="*Загрузите изображение и нажмите 'Анализировать'*")

            # ===== Вкладка: Рефлексия (Innovation 009) =====
            with gr.Tab("🪞 Рефлексия"):
                gr.Markdown("*Метакогнитивная рефлексия после сессии*")

                reflection_btn = gr.Button("🪞 Получить рефлексию", variant="primary")
                reflection_out = gr.Markdown(value="*Нажмите 'Получить рефлексию' для анализа сессии*")

                gr.Markdown("""
---
**Рекомендации:**
- Проводите рефлексию после занятий 30+ минут
- Отвечайте на вопросы письменно для лучшего усвоения
- Отслеживайте свой метакогнитивный прогресс
                """)

        # ===== Обработчики =====

        init_btn.click(fn=app.initialize, outputs=[status])

        # Chat handler (streaming with inline thinking)
        def handle_chat(message, history):
            for result in app.chat_stream(message, history):
                yield result

        chat_btn.click(
            fn=handle_chat,
            inputs=[chat_input, chat_box],
            outputs=[chat_input, chat_box]
        )
        chat_input.submit(
            fn=handle_chat,
            inputs=[chat_input, chat_box],
            outputs=[chat_input, chat_box]
        )

        # Математика
        math_get_btn.click(fn=app.get_math_task, inputs=[math_topic, math_diff], outputs=[math_problem, math_info])
        math_check_btn.click(fn=app.check_math_answer, inputs=[math_answer, math_chat], outputs=[math_answer, math_chat])
        math_answer.submit(fn=app.check_math_answer, inputs=[math_answer, math_chat], outputs=[math_answer, math_chat])
        math_hint_btn.click(fn=app.get_math_hint, outputs=[math_hint_out])
        math_sol_btn.click(fn=app.show_math_solution, outputs=[math_hint_out])
        
        # Алгоритмы
        algo_get_btn.click(
            fn=lambda d, c: app.get_algo_task("", d, c),
            inputs=[algo_diff, algo_cat],
            outputs=[algo_problem, algo_code, algo_info]
        )
        algo_load_btn.click(
            fn=lambda id: app.get_algo_task(id),
            inputs=[algo_id],
            outputs=[algo_problem, algo_code, algo_info]
        )
        algo_run_btn.click(fn=app.run_code, inputs=[algo_code], outputs=[algo_results])
        algo_analyze_btn.click(fn=app.analyze_code, inputs=[algo_code], outputs=[algo_results])
        algo_submit_btn.click(fn=app.submit_code, inputs=[algo_code], outputs=[algo_results])
        algo_hint_btn.click(fn=app.get_algo_hint, outputs=[algo_hint_out])
        algo_sol_btn.click(fn=app.show_algo_solution, outputs=[algo_hint_out, algo_solution]).then(
            fn=lambda: gr.update(visible=True), outputs=[algo_solution]
        )
        
        # Профиль
        profile_btn.click(fn=app.get_profile, outputs=[profile_out])
        analytics_btn.click(fn=app.get_analytics, outputs=[profile_out])

        # Когнитивная нагрузка
        cognitive_btn.click(fn=app.get_cognitive_load, outputs=[cognitive_out])

        # Память
        memory_btn.click(fn=app.get_memory_status, outputs=[memory_out])
        cache_stats_btn.click(fn=app.get_cache_stats, outputs=[memory_out])
        clear_memory_btn.click(fn=app.clear_session_memory, outputs=[memory_out])

        # === Innovation handlers (009) ===

        # Task Generator
        gen_btn.click(
            fn=app.generate_new_task,
            inputs=[gen_topic, gen_diff],
            outputs=[gen_problem, gen_info]
        )

        # Learning Path
        path_btn.click(
            fn=app.get_learning_path,
            inputs=[path_skill],
            outputs=[path_out]
        )

        # OCR Analysis
        ocr_btn.click(
            fn=app.analyze_handwritten_solution,
            inputs=[ocr_image, ocr_problem],
            outputs=[ocr_result]
        )

        # Reflection
        reflection_btn.click(
            fn=app.get_session_reflection,
            outputs=[reflection_out]
        )

    return interface


if __name__ == "__main__":
    print("MITS")
    print(f"Model: {settings.MODEL_NAME}")
    print("http://localhost:7860")
    print()

    interface = create_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
