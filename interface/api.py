"""
MITS FastAPI Server

REST API for the tutoring system.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uuid

from src.models.llm_client import LLMClient
from src.agents.tutor_agent import SocraticTutorAgent
from src.agents.task_generator import TaskGeneratorAgent
from src.agents.response_verifier import ResponseVerifierAgent
from src.data.schemas import Task, TutoringSession, Difficulty, TutorResponse
from src.config import settings


# ═══════════════════════════════════════════════════════════════════════════
# API Models
# ═══════════════════════════════════════════════════════════════════════════

class StartSessionRequest(BaseModel):
    topic: str = "derivatives"
    difficulty: str = "medium"
    custom_problem: Optional[str] = None

class StartSessionResponse(BaseModel):
    session_id: str
    problem: str
    welcome_message: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    move: str
    message: str
    is_solved: bool
    hints_used: int

class HintResponse(BaseModel):
    hint_number: int
    hint_text: str
    hints_remaining: int


# ═══════════════════════════════════════════════════════════════════════════
# Application
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="MITS API",
    description="Mathematics Intelligent Tutoring System API",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# State
sessions: dict = {}
llm_client: Optional[LLMClient] = None
tutor: Optional[SocraticTutorAgent] = None
task_generator: Optional[TaskGeneratorAgent] = None
verifier: Optional[ResponseVerifierAgent] = None


# ═══════════════════════════════════════════════════════════════════════════
# Lifecycle
# ═══════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    """Initialize components on startup."""
    global llm_client, tutor, task_generator, verifier
    
    llm_client = LLMClient()
    tutor = SocraticTutorAgent(llm_client)
    task_generator = TaskGeneratorAgent(llm_client)
    verifier = ResponseVerifierAgent(llm_client)
    
    print(f"✅ MITS API initialized with {settings.MODEL_NAME}")


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Health check."""
    return {
        "status": "ok",
        "service": "MITS API",
        "model": settings.MODEL_NAME
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    ollama_ok = llm_client.check_connection() if llm_client else False
    
    return {
        "status": "healthy" if ollama_ok else "degraded",
        "ollama_connected": ollama_ok,
        "active_sessions": len(sessions)
    }


@app.post("/session/start", response_model=StartSessionResponse)
async def start_session(request: StartSessionRequest):
    """Start a new tutoring session."""
    try:
        difficulty = Difficulty(request.difficulty)
        
        # Generate task
        if request.custom_problem:
            task = Task(
                id=str(uuid.uuid4()),
                topic=request.topic,
                difficulty=difficulty,
                problem=request.custom_problem,
                solution="Custom problem",
                answer="[Custom]",
                skills=[request.topic]
            )
        else:
            task = task_generator.generate_task(
                topic=request.topic,
                difficulty=difficulty
            )
        
        # Create session
        session = TutoringSession(
            id=str(uuid.uuid4()),
            student_id="api_user",
            task=task
        )
        
        sessions[session.id] = session
        
        welcome = f"Let's work on this problem together!\n\n{task.problem}\n\nWhat's your approach?"
        
        return StartSessionResponse(
            session_id=session.id,
            problem=task.problem,
            welcome_message=welcome
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send message and get tutor response."""
    session = sessions.get(request.session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # Add student message
        session.add_student_message(request.message)
        
        # Verify answer
        verification = verifier.verify(session.task, request.message)
        
        if verification.is_correct:
            session.is_solved = True
            return ChatResponse(
                move="success",
                message="🎉 Excellent! That's correct!",
                is_solved=True,
                hints_used=session.hints_used
            )
        
        # Generate response
        response = tutor.generate_response(
            session=session,
            student_message=request.message,
            verification_result=verification
        )
        
        session.add_tutor_response(response)
        
        return ChatResponse(
            move=response.move.value,
            message=response.message,
            is_solved=session.is_solved,
            hints_used=session.hints_used
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}/hint", response_model=HintResponse)
async def get_hint(session_id: str):
    """Get next hint for session."""
    session = sessions.get(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.hints_used >= len(session.task.hints):
        raise HTTPException(status_code=400, detail="No more hints available")
    
    hint = session.task.hints[session.hints_used]
    session.hints_used += 1
    
    return HintResponse(
        hint_number=session.hints_used,
        hint_text=hint,
        hints_remaining=len(session.task.hints) - session.hints_used
    )


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    session = sessions.get(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "id": session.id,
        "topic": session.task.topic,
        "difficulty": session.task.difficulty.value,
        "attempts": session.attempts,
        "hints_used": session.hints_used,
        "is_solved": session.is_solved,
        "conversation_length": len(session.conversation)
    }


@app.delete("/session/{session_id}")
async def end_session(session_id: str):
    """End and delete session."""
    if session_id in sessions:
        del sessions[session_id]
        return {"status": "deleted"}
    
    raise HTTPException(status_code=404, detail="Session not found")
