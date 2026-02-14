# Research: MITS System Completion

**Feature**: 006-mits-system-completion
**Date**: 2026-02-02
**Status**: Complete

## 1. Knowledge Tracing Models

### Decision: Hybrid BKT + Lightweight DKT

**Rationale**: Research from 2025 shows that:
- BKT is effective for new students (<10 interactions) due to its interpretability and low data requirements
- DKT (Deep Knowledge Tracing) significantly outperforms BKT after sufficient data (≥10 responses)
- RL-DKT achieves 12.5% improvement in task completion time and 50% reduction in dropout rates

**Implementation Approach**:
- Keep existing BKT implementation for cold-start
- Add lightweight LSTM-based DKT (not transformer to stay within 8GB VRAM)
- Transition threshold: 10 student responses
- Use DKT-Forget variant to model knowledge decay

**Alternatives Considered**:
| Model | Pros | Cons | Decision |
|-------|------|------|----------|
| BKT only | Simple, interpretable | Cannot model complex skill dependencies | Keep for cold-start |
| DKT (RNN) | Captures temporal patterns | Needs training data | Add as enhancement |
| ATKT | Attention-based, robust | Higher VRAM requirement | Future consideration |
| Transformer KT | State-of-the-art accuracy | Too large for 8GB VRAM | Rejected |

**Sources**:
- [Deep Knowledge Tracing Review 2025](https://dl.acm.org/doi/10.1145/3729605.3729620)
- [RL-DKT for Personalized Learning](https://www.nature.com/articles/s41598-025-23900-4)
- [Cognitive Load Integration with DKT](https://www.nature.com/articles/s41598-025-10497-x)

---

## 2. Cognitive Load Estimation

### Decision: Multi-Signal Estimation Model

**Rationale**: 2025 research demonstrates that combining DKT with cognitive load estimation enables "learning paths that are optimally challenging—difficult enough to promote growth but not so demanding as to cause frustration."

**Implementation Approach**:
- **Response Time**: Longer than average = higher load
- **Error Patterns**: Multiple consecutive errors = cognitive overload
- **Interaction Frequency**: Rapid interactions = low load; long pauses = potential struggle
- **Task Complexity**: AST-based code complexity metrics for programming tasks

**Cognitive Load Levels**:
```python
class CognitiveLoad(Enum):
    LOW = 1      # Student performing well, can increase difficulty
    OPTIMAL = 2  # Ideal learning zone
    HIGH = 3     # Signs of struggle, maintain current level
    OVERLOAD = 4 # Multiple indicators of overload, simplify
```

**Sources**:
- [Deep Knowledge Tracing and Cognitive Load Estimation](https://pmc.ncbi.nlm.nih.gov/articles/PMC12246154/)

---

## 3. RAG for Educational Systems

### Decision: Context-Aware RAG with Re-ranking

**Rationale**: 2025 systematic reviews show that RAG eliminates the main barrier for LLM adoption in education: hallucinations. Studies report only 1.5% incorrect answers with RAG vs. significant hallucination rates without it.

**Implementation Approach**:
1. **Knowledge Base Structure**:
   - Hints: Progressive (conceptual → procedural → specific)
   - Misconceptions: Common errors with Socratic correction questions
   - Worked Examples: Step-by-step solutions for retrieval

2. **Re-ranking Strategy**:
   - Initial retrieval: Semantic similarity (sentence-transformers)
   - Re-rank by: Student knowledge state, topic relevance, hint progression level

3. **Fallback Mechanism**:
   - If RAG score < threshold: Use LLM generation with disclaimer
   - Log fallback cases for knowledge base expansion

**MCP+ACP Protocol Findings**:
Research shows that MCP (Model Context Protocol) for session/task/course context integration:
- Improves Recall@1 for hint retrieval
- Increases citation fidelity
- Reduces unsupported claims

**Sources**:
- [RAG for Educational Applications Survey](https://www.sciencedirect.com/science/article/pii/S2666920X25000578)
- [RAG Chatbots for Education Survey](https://www.mdpi.com/2076-3417/15/8/4234)
- [MCP+ACP for Intelligent Tutoring](https://www.mdpi.com/2076-3417/15/21/11443)
- [LPITutor: RAG + Prompt Engineering](https://peerj.com/articles/cs-2991/)

---

## 4. Socratic Tutoring Methods

### Decision: SocraticLLM-Inspired Approach

**Rationale**: Research from 2025-2026 shows that Socratic method with LLMs:
- Develops critical thinking and long-term retention
- Promotes self-explanation and metacognitive skills
- Requires structured, thought-provoking questions rather than direct answers

**Socratic Playground for Learning (SPL) Architecture**:
- **Content Retriever**: Get relevant educational content
- **Instructional Advisor**: Suggest pedagogical approach
- **Feedback Assessor**: Evaluate student responses
- **User Interface**: Render Socratic dialogue

**Implementation in MITS**:
- Map SPL components to existing agents:
  - Content Retriever → RAG Retriever
  - Instructional Advisor → Planner Agent
  - Feedback Assessor → Verifier Agent + Profiler Agent
- Add explicit Socratic question templates
- Implement progressive scaffolding levels

**Sources**:
- [SocraticLLM Teaching Math](https://www.starspark.ai/blog/socratic-llm-tutors)
- [Socratic Chatbot for Critical Thinking](https://arxiv.org/html/2409.05511v1)
- [GPT-4 Modular ITS Framework](https://www.mdpi.com/2079-9292/13/24/4876)

---

## 5. Multi-Agent Architecture

### Decision: GenMentor-Style Pipeline (Already Implemented)

**Rationale**: MITS already implements the recommended multi-agent pattern from recent research:
- Profiler → Planner → Tutor → Verifier pipeline
- Orchestrator for coordination
- Specialized agents for specific tasks

**Enhancements Based on Research**:
1. Add cognitive load signals to Planner decision-making
2. Strengthen Verifier checks for answer-leak prevention
3. Add dual-memory integration to all agents

**Sources**:
- [Simulation of Teaching Behaviours in ITS](https://link.springer.com/article/10.1007/s10462-025-11464-8)
- [AI-Powered Math Tutoring Platform](https://arxiv.org/html/2507.12484v1)

---

## 6. Memory and Personalization

### Decision: Dual-Memory with Knowledge Decay

**Rationale**: Research emphasizes importance of:
- Short-term memory: Session context, recent problems, current dialogue
- Long-term memory: Student profile, knowledge state, learning preferences
- Knowledge decay: Topics not practiced recently should show reduced mastery

**Implementation**:
```python
# Session Memory (in-memory, per session)
- conversation_history: List[Turn]
- current_task: Task
- session_metrics: Dict[str, float]
- referenced_hints: List[str]

# Student Memory (SQLite, persistent)
- student_id: str
- knowledge_state: Dict[topic, mastery]
- preferences: Dict[str, Any]
- learning_history: List[Interaction]
- last_seen: Dict[topic, datetime]
```

**Knowledge Decay Model**:
- Ebbinghaus-inspired forgetting curve
- `mastery_now = mastery_last * exp(-decay_rate * days_since_practice)`
- Default decay_rate: 0.05 (configurable per topic)

**Sources**:
- [AI-Driven ITS in K-12 Systematic Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12078640/)
- [DKT-Forget Model](https://educationaldatamining.org/EDM2025/proceedings/2025.EDM.industry-papers.46/index.html)

---

## 7. Russian Language Support

### Decision: GLM-4.7-Flash Native Multilingual

**Rationale**: GLM-4 models have strong multilingual capabilities including Russian. Testing confirms quality Russian output with proper mathematical terminology.

**Implementation Notes**:
- Use Russian prompts (already in prompts.py)
- Russian mathematical notation: tg (not tan), ctg (not cot), lg (not log10)
- UTF-8 encoding throughout
- Test with Russian-speaking evaluators

---

## 8. Performance Optimization

### Decision: Pre-computed Embeddings + Caching

**Rationale**: To meet <5s hint delivery requirement:
1. Pre-compute all knowledge base embeddings at startup
2. Use ChromaDB's efficient ANN (Approximate Nearest Neighbor) search
3. Cache frequent queries and responses
4. Async LLM calls where possible

**Benchmarks** (from existing implementation):
- RAG retrieval: ~200ms (acceptable)
- LLM generation: 2-4s (primary bottleneck)
- Total target: <5s (achievable)

---

## Summary of Technical Decisions

| Area | Decision | Key Benefit |
|------|----------|-------------|
| Knowledge Tracing | BKT + DKT hybrid | Best of both: interpretability + accuracy |
| Cognitive Load | Multi-signal estimation | Adaptive difficulty management |
| RAG | Context-aware re-ranking | Reduced hallucinations, better hints |
| Socratic Method | SPL-inspired architecture | Structured questioning approach |
| Memory | Dual-memory + decay | Personalization + realistic forgetting |
| Language | GLM-4 native multilingual | Quality Russian support |
| Performance | Pre-compute + cache | <5s response time |
