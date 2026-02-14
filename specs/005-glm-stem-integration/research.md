# Research: GLM-STEM Model Integration

**Feature**: 005-glm-stem-integration
**Date**: 2026-02-02

## Research Tasks Completed

### 1. GGUF Download Best Practices

**Decision**: Use `huggingface_hub` Python library with `hf_hub_download()`

**Rationale**:
- Native resume support for interrupted downloads
- Automatic cache management
- Progress reporting built-in
- Cross-platform compatibility

**Alternatives Considered**:
- `wget/curl`: No native resume, platform-specific
- `requests`: Requires manual chunking and resume logic
- Direct browser download: No automation possible

### 2. Ollama Model Registration

**Decision**: Use `ollama create` with Modelfile

**Rationale**:
- Standard Ollama workflow
- Supports all model parameters (temperature, top_k, etc.)
- Easy to reproduce and version control

**Modelfile Template**:
```
FROM ./glm-stem-42exp-q4km.gguf

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER top_k 2
PARAMETER repeat_penalty 1.0
PARAMETER num_ctx 4096

SYSTEM """You are a Socratic math tutor..."""
```

### 3. Cross-Platform Installation Script

**Decision**: Separate scripts for Bash (Linux/macOS) and PowerShell (Windows)

**Rationale**:
- PowerShell is default on Windows, Bash on Unix
- Avoids WSL dependency on Windows
- Each script can use native tools (curl vs Invoke-WebRequest)

**Alternatives Considered**:
- Single Python script: Requires Python pre-installed
- Makefile: Poor Windows support
- Docker: Overkill for simple installation

### 4. Model Quality Testing

**Decision**: pytest with Ollama fixtures, 20 STEM test cases

**Test Categories**:
1. **Algebra** (5 tests): Linear equations, quadratics
2. **Calculus** (3 tests): Derivatives, integrals
3. **Programming** (5 tests): Python syntax, algorithms
4. **Physics** (4 tests): Mechanics, basic formulas
5. **Russian Language** (3 tests): Bilingual capability

**Rationale**:
- Covers all STEM domains from constitution
- Quick to run (<5 min with model loaded)
- Deterministic (temperature=0 for tests)

### 5. Fallback Mechanism

**Decision**: Check model availability at startup, log warning if using fallback

**Implementation**:
```python
def get_available_model():
    try:
        models = ollama.list()
        if 'glm-stem-42exp' in [m.name for m in models]:
            return 'glm-stem-42exp'
    except:
        pass
    return settings.MODEL_FALLBACK  # glm-4.7-flash
```

**Rationale**:
- Graceful degradation without user intervention
- Clear logging for debugging
- No breaking changes to existing setups

### 6. Disk Space Check

**Decision**: Check for 20GB free space before download

**Rationale**:
- Q4_K_M is ~13GB, Q8_0 is ~21GB
- Extra space for temp files during extraction
- Prevents partial downloads that waste time

**Implementation**:
- Linux/macOS: `df -B1 . | tail -1 | awk '{print $4}'`
- Windows: `(Get-PSDrive C).Free`

## Unresolved Items

None - all technical decisions made.

## Dependencies Identified

| Dependency | Version | Purpose |
|------------|---------|---------|
| huggingface_hub | >=0.20 | GGUF download with resume |
| ollama | >=0.1.0 | Python bindings for Ollama |
| pytest | >=7.0 | Test framework |
| pytest-timeout | >=2.0 | Timeout for model tests |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| HuggingFace rate limiting | Low | Medium | Use authenticated requests |
| Ollama version incompatibility | Low | High | Document minimum version |
| GGUF format changes | Very Low | High | Pin to specific model revision |
| Insufficient VRAM | Medium | High | Detect and warn before loading |
