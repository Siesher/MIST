"""
MITS Gradio Interface

Web interface for the Socratic tutoring system.
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
from src.models.prompts import WELCOME_MESSAGE, SUCCESS_MESSAGE
from src.config import settings


class TutoringApp:
    """
    Main application managing tutoring sessions.
    """
    
    def __init__(self):
        """Initialize the tutoring application."""
        self.llm_client: Optional[LLMClient] = None
        self.tutor: Optional[SocraticTutorAgent] = None
        self.task_generator: Optional[TaskGeneratorAgent] = None
        self.verifier: Optional[ResponseVerifierAgent] = None
        
        self.current_session: Optional[TutoringSession] = None
        self.is_initialized = False
    
    def initialize(self) -> str:
        """Initialize LLM client and agents."""
        try:
            self.llm_client = LLMClient()
            
            # Check connection
            if not self.llm_client.check_connection():
                return "❌ Cannot connect to Ollama. Please run: ollama serve"
            
            # Check if model is available
            models = self.llm_client.list_models()
            if not any(settings.MODEL_NAME.split(':')[0] in m for m in models):
                return f"❌ Model {settings.MODEL_NAME} not found. Run: ollama pull {settings.MODEL_NAME}"
            
            # Initialize agents
            self.tutor = SocraticTutorAgent(self.llm_client)
            self.task_generator = TaskGeneratorAgent(self.llm_client)
            self.verifier = ResponseVerifierAgent(self.llm_client)
            
            self.is_initialized = True
            return f"✅ System initialized with {settings.MODEL_NAME}"
            
        except Exception as e:
            return f"❌ Initialization failed: {str(e)}"
    
    def start_session(
        self,
        topic: str,
        difficulty: str,
        custom_problem: str = ""
    ) -> Tuple[str, str, List]:
        """Start a new tutoring session."""
        if not self.is_initialized:
            return "Please initialize the system first!", "", []
        
        try:
            difficulty_enum = Difficulty(difficulty)
            
            # Generate or use custom task
            if custom_problem.strip():
                task = Task(
                    id=str(uuid.uuid4()),
                    topic=topic,
                    difficulty=difficulty_enum,
                    problem=custom_problem,
                    solution="Custom problem - solution not provided",
                    answer="[Custom]",
                    skills=[topic]
                )
            else:
                task = self.task_generator.generate_task(
                    topic=topic,
                    difficulty=difficulty_enum
                )
            
            # Create session
            self.current_session = TutoringSession(
                id=str(uuid.uuid4()),
                student_id="gradio_user",
                task=task
            )
            
            # Welcome message
            welcome = WELCOME_MESSAGE.format(problem=task.problem)
            
            task_info = f"""**Topic:** {topic}
**Difficulty:** {difficulty}
**Skills:** {', '.join(task.skills)}
**Hints available:** {len(task.hints)}"""
            
            return welcome, task_info, [(None, welcome)]
            
        except Exception as e:
            return f"❌ Error starting session: {str(e)}", "", []
    
    def process_message(
        self,
        message: str,
        history: List
    ) -> Tuple[str, List]:
        """Process student message and get tutor response."""
        if not self.current_session:
            return "Please start a session first!", history
        
        if not message.strip():
            return "", history
        
        try:
            # Add student message to session
            self.current_session.add_student_message(message)
            
            # Verify student's answer
            verification = self.verifier.verify(
                self.current_session.task,
                message
            )
            
            # Check if solved
            if verification.is_correct:
                self.current_session.is_solved = True
                success_msg = SUCCESS_MESSAGE.format(student_answer=message)
                history.append((message, success_msg))
                return "", history
            
            # Generate tutor response
            response = self.tutor.generate_response(
                session=self.current_session,
                student_message=message,
                verification_result=verification
            )
            
            # Add tutor response to session
            self.current_session.add_tutor_response(response)
            
            # Format response with move indicator
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
            
            history.append((message, formatted_response))
            return "", history
            
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            history.append((message, error_msg))
            return "", history
    
    def get_hint(self) -> str:
        """Get next available hint."""
        if not self.current_session:
            return "Start a session first!"
        
        task = self.current_session.task
        hints_used = self.current_session.hints_used
        
        if hints_used >= len(task.hints):
            return "❌ No more hints available!"
        
        hint = task.hints[hints_used]
        self.current_session.hints_used += 1
        
        return f"💡 **Hint {hints_used + 1}/{len(task.hints)}:** {hint}"
    
    def show_solution(self) -> str:
        """Show the solution (for learning purposes)."""
        if not self.current_session:
            return "Start a session first!"
        
        task = self.current_session.task
        self.current_session.told_answer = True
        
        return f"""## Solution

{task.solution}

**Answer:** {task.answer}

---
⚠️ *This session is now marked as "answer revealed" for analytics.*"""
    
    def get_session_stats(self) -> str:
        """Get current session statistics."""
        if not self.current_session:
            return "No active session"
        
        session = self.current_session
        
        return f"""## Session Statistics

- **Attempts:** {session.attempts}
- **Hints used:** {session.hints_used}/{len(session.task.hints)}
- **Turns:** {len(session.conversation)}
- **Status:** {'✅ Solved!' if session.is_solved else '🔄 In progress'}
- **Answer revealed:** {'⚠️ Yes' if session.told_answer else '✅ No'}"""


# Create application instance
app = TutoringApp()


def create_interface() -> gr.Blocks:
    """Create the Gradio interface."""
    
    with gr.Blocks(
        title="🎓 MITS - Socratic Math Tutor",
        theme=gr.themes.Soft()
    ) as interface:
        
        gr.Markdown("""
# 🎓 MITS - Mathematics Intelligent Tutoring System

An AI tutor that guides you to discover solutions through the **Socratic method** — asking questions, not giving answers!
        """)
        
        # System status
        with gr.Row():
            status_text = gr.Textbox(
                label="System Status",
                value="Click 'Initialize' to start",
                interactive=False
            )
            init_btn = gr.Button("🚀 Initialize System", variant="primary")
        
        with gr.Row():
            # Left column - Controls
            with gr.Column(scale=1):
                gr.Markdown("### 📚 New Session")
                
                topic_dropdown = gr.Dropdown(
                    choices=[
                        "derivatives", "integrals", "limits",
                        "linear_equations", "quadratic_equations",
                        "chain_rule", "product_rule", "quotient_rule",
                        "trigonometry", "vectors"
                    ],
                    value="derivatives",
                    label="Topic"
                )
                
                difficulty_dropdown = gr.Dropdown(
                    choices=["easy", "medium", "hard", "olympiad"],
                    value="medium",
                    label="Difficulty"
                )
                
                custom_problem = gr.Textbox(
                    label="Custom Problem (optional)",
                    placeholder="Enter your own problem or leave empty for auto-generation",
                    lines=2
                )
                
                start_btn = gr.Button("▶️ Start New Problem", variant="primary")
                
                gr.Markdown("### 📋 Current Task")
                task_info = gr.Markdown("*No active task*")
                
                gr.Markdown("### 🛠️ Tools")
                hint_btn = gr.Button("💡 Get Hint")
                hint_output = gr.Markdown()
                
                solution_btn = gr.Button("📖 Show Solution")
                solution_output = gr.Markdown()
                
                stats_btn = gr.Button("📊 Session Stats")
                stats_output = gr.Markdown()
            
            # Right column - Chat
            with gr.Column(scale=2):
                gr.Markdown("### 💬 Tutoring Session")
                
                chatbot = gr.Chatbot(
                    height=500,
                    label="Conversation",
                    show_label=False
                )
                
                with gr.Row():
                    msg_input = gr.Textbox(
                        label="Your message",
                        placeholder="Type your thoughts, questions, or solution...",
                        lines=2,
                        scale=4
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)
        
        gr.Markdown("""
---
### 📖 How to use:
1. Click **Initialize System** to connect to Ollama
2. Select a **topic** and **difficulty**, then click **Start New Problem**
3. Type your thoughts and attempts in the chat
4. The tutor will guide you with questions, not answers!
5. Use **Hints** if stuck, or **Show Solution** to learn

*The Socratic method helps you truly understand, not just memorize!*
        """)
        
        # Event handlers
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


# Main entry point
if __name__ == "__main__":
    print("🎓 Starting MITS - Socratic Math Tutor...")
    print(f"📡 Ollama host: {settings.OLLAMA_HOST}")
    print(f"🤖 Model: {settings.MODEL_NAME}")
    print()
    
    interface = create_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
