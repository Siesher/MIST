# Quickstart: MITS Comprehensive Improvements

**Feature**: 013-comprehensive-improvements
**Date**: 2026-02-05

## Prerequisites

- Python 3.11+
- Node.js 20+
- Ollama installed with GLM-4.7-Flash model
- Google Colab Pro+ account (for training notebooks)
- Docker + Docker Compose (for deployment)

## Validation Tests

### Test 1: Session Persistence
```
1. Start backend: uvicorn backend.app.main:app --port 8000
2. Create a session via API: POST /api/v1/sessions
3. Send a message: POST /api/v1/chat/{session_id}
4. Stop the backend (Ctrl+C)
5. Restart the backend
6. GET /api/v1/sessions/{session_id}
7. VERIFY: Session exists with all messages preserved
```

### Test 2: Authentication
```
1. Register: POST /api/v1/auth/register { email, password, display_name }
2. VERIFY: Receive access_token and refresh_token
3. Create session with token: POST /api/v1/sessions (Authorization: Bearer <token>)
4. Register second user
5. GET /api/v1/sessions with second user's token
6. VERIFY: Second user sees zero sessions (data isolated)
```

### Test 3: Analytics Dashboard
```
1. Login as user with 5+ sessions
2. Navigate to /dashboard (or /profile analytics tab)
3. VERIFY: Mastery line chart renders with real data
4. VERIFY: Activity heatmap shows study days
5. VERIFY: Error distribution chart shows categories
6. VERIFY: Study recommendations list 3 topics
```

### Test 4: PDF Export
```
1. Login as user with session history
2. Click "Export Progress" or GET /api/v1/export/report.pdf
3. VERIFY: PDF downloads
4. VERIFY: PDF contains: student summary, session list, mastery chart, error types, recommendations
```

### Test 5: LLM Cache
```
1. Send message: "Объясни что такое производная"
2. Note response time (T1)
3. Send exact same message again
4. Note response time (T2)
5. VERIFY: T2 < T1 * 0.3 (at least 70% faster)
```

### Test 6: Fine-tuned Model (Colab)
```
1. Open notebooks/finetuning_glm.ipynb in Colab Pro+
2. Run all cells
3. VERIFY: Training completes, checkpoint saved
4. Run evaluation cells
5. VERIFY: Fine-tuned Socratic Score > base model Socratic Score
```

### Test 7: DKT Training (Colab)
```
1. Open notebooks/dkt_training.ipynb in Colab Pro+
2. Run data download + preprocessing
3. Run training
4. VERIFY: Test AUC > 0.75
5. VERIFY: Weights exported to data/models/dkt_pretrained.pt
```

### Test 8: Emotion Detection (Colab)
```
1. Open notebooks/affective_rubert.ipynb in Colab Pro+
2. Run training on labeled dataset
3. VERIFY: Macro F1 > 0.65
4. Run comparison with rule-based detector
5. VERIFY: ML F1 > rule-based F1
```

### Test 9: Vision OCR
```
1. Take photo of handwritten math solution (e.g., derivative of x²+3x)
2. Upload via POST /api/v1/vision/recognize
3. VERIFY: LaTeX output matches handwritten expression
4. POST /api/v1/vision/verify with the LaTeX
5. VERIFY: Steps are checked, errors identified if present
```

### Test 10: Docker Deployment
```
1. On clean machine: git clone <repo>
2. docker compose up --build
3. Wait for all services healthy (< 5 min)
4. Open http://localhost:3000
5. Register, create session, send message
6. VERIFY: Streamed response from LLM
```

### Test 11: Evaluation Pipeline
```
1. Run: python -m evaluation.run_evaluation --benchmark all
2. VERIFY: Report generated in evaluation/reports/
3. VERIFY: Contains Socratic Score, Telling Rate, Error Recovery
4. VERIFY: Model comparison tables generated (if both models available)
```

### Test 12: A/B Experiment
```
1. Create experiment: POST /api/v1/experiments
2. Enroll 2 test users to different groups
3. Submit pre-test scores
4. Complete 3 sessions per user
5. Submit post-test scores
6. GET /api/v1/experiments/{id}/results
7. VERIFY: Statistical report with t-test, Cohen's d generated
```

## Smoke Test (All Features)

```bash
# 1. Start with Docker
docker compose up -d

# 2. Register user
curl -X POST localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test1234","display_name":"Test"}'

# 3. Create session in guided_learning mode
curl -X POST localhost:8000/api/v1/sessions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"mode":"guided_learning"}'

# 4. Send message
curl -X POST localhost:8000/api/v1/chat/<session_id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"content":"Помоги разобраться с производными"}'

# 5. Check analytics
curl localhost:8000/api/v1/analytics/mastery \
  -H "Authorization: Bearer <token>"

# 6. Export PDF
curl -o report.pdf localhost:8000/api/v1/export/report.pdf \
  -H "Authorization: Bearer <token>"
```
