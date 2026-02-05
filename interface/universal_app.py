"""
MITS Gradio Interface - Универсальная версия

Простой диалоговый интерфейс для любых предметов.
"""

import gradio as gr
from typing import Optional, Tuple, List
import json

from src.models.llm_client import LLMClient
from src.models.prompts import (
    UNIVERSAL_TUTOR_SYSTEM, 
    UNIVERSAL_RESPONSE_PROMPT,
    WELCOME_MESSAGE_UNIVERSAL
)
from src.config import settings


class UniversalTutor:
    """Универсальный репетитор для любых предметов."""
    
    def __init__(self):
        self.llm_client: Optional[LLMClient] = None
        self.is_initialized = False
        self.conversation_history = []
    
    def initialize(self) -> str:
        """Инициализация LLM."""
        try:
            self.llm_client = LLMClient()
            
            if not self.llm_client.check_connection():
                return "❌ Не удалось подключиться к Ollama. Запустите: ollama serve"
            
            models = self.llm_client.list_models()
            if not any(settings.MODEL_NAME.split(':')[0] in m for m in models):
                return f"❌ Модель {settings.MODEL_NAME} не найдена. Выполните: ollama pull {settings.MODEL_NAME}"
            
            self.is_initialized = True
            return f"✅ Система готова! Модель: {settings.MODEL_NAME}"
            
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"
    
    def chat(self, message: str, history: List) -> Tuple[str, List]:
        """Обработка сообщения."""
        if not self.is_initialized:
            return "", history + [{"role": "user", "content": message}, 
                                   {"role": "assistant", "content": "⚠️ Сначала нажмите 'Запустить систему'!"}]
        
        if not message.strip():
            return "", history
        
        try:
            # Формируем историю для промпта
            history_text = ""
            for msg in history[-10:]:  # Последние 10 сообщений
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
            
            # Парсим JSON ответ
            try:
                data = json.loads(response)
                tutor_message = data.get("message", response)
                move = data.get("move", "scaffolding")
                
                # Эмодзи для типа ответа
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
            
            # Обновляем историю
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
    
    def clear_chat(self) -> Tuple[str, List]:
        """Очистить чат."""
        return "", [{"role": "assistant", "content": WELCOME_MESSAGE_UNIVERSAL}]


# Создаём экземпляр
tutor = UniversalTutor()


def create_interface() -> gr.Blocks:
    """Создать интерфейс."""
    
    with gr.Blocks(title="🐝 MITS - Сократический Репетитор") as interface:
        
        gr.Markdown("""
# 🐝 MITS — Умный Репетитор

**Сократический метод:** Я не даю готовых ответов, а помогаю тебе самому прийти к решению!
        """)
        
        with gr.Row():
            status = gr.Textbox(
                label="📡 Статус",
                value="Нажмите 'Запустить' для начала",
                interactive=False,
                scale=3
            )
            init_btn = gr.Button("🚀 Запустить", variant="primary", scale=1)
        
        chatbot = gr.Chatbot(
            value=[{"role": "assistant", "content": WELCOME_MESSAGE_UNIVERSAL}],
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
                label="💬 Твоё сообщение",
                placeholder="Напиши задачу, вопрос или свои мысли...",
                lines=2,
                scale=5
            )
            send_btn = gr.Button("📤 Отправить", variant="primary", scale=1)
        
        with gr.Row():
            clear_btn = gr.Button("🗑️ Новый диалог", variant="secondary")
        
        gr.Markdown("""
---
### 💡 Примеры вопросов:

**Математика:** *"Найди производную функции $f(x) = x^3 \\cdot \\sin(x)$"*

**Программирование:** *"Как работает рекурсия? Объясни на примере"*

**Физика:** *"Почему небо голубое?"*

**Любой предмет:** Просто задай свой вопрос!
        """)
        
        # Обработчики
        init_btn.click(fn=tutor.initialize, outputs=[status])
        
        send_btn.click(
            fn=tutor.chat,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot]
        )
        
        msg_input.submit(
            fn=tutor.chat,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot]
        )
        
        clear_btn.click(
            fn=tutor.clear_chat,
            outputs=[msg_input, chatbot]
        )
    
    return interface


if __name__ == "__main__":
    print("🐝 Запуск MITS — Универсальный Сократический Репетитор")
    print(f"📡 Ollama: {settings.OLLAMA_HOST}")
    print(f"🤖 Модель: {settings.MODEL_NAME}")
    print()
    print("🌐 Откройте: http://localhost:7860")
    print()
    
    interface = create_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
