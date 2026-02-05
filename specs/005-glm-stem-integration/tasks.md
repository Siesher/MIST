# Tasks: GLM-STEM Model Integration

**Input**: Design documents from `/specs/005-glm-stem-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included as User Story 3 focuses on model quality testing.

**Organization**: Tasks grouped by user story for independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Prepare scripts directory and dependencies

- [x] T001 Create scripts directory at scripts/ if not exists
- [x] T002 [P] Add huggingface_hub to requirements.txt

---

## Phase 2: Foundational (Configuration Updates)

**Purpose**: Update existing config to support new model - MUST complete before user stories

**⚠️ CRITICAL**: Configuration must be correct before installation script can work

- [x] T003 Update MODEL_NAME default to "glm-stem-42exp" in src/config.py
- [x] T004 Update MODEL_FALLBACK to "glm-4.7-flash" in src/config.py
- [x] T005 Add "glm-stem-42exp-tutor" preset to MODEL_PRESETS in src/inference/model_manager.py
- [x] T006 Update default tutor preset to "glm-stem-42exp-tutor" in src/inference/model_manager.py
- [x] T007 Update .env.example with new model settings and installation instructions

**Checkpoint**: ✅ Configuration ready - installation scripts can now be created

---

## Phase 3: User Story 1 - Model Installation (Priority: P1) 🎯 MVP

**Goal**: Developer can install pruned GLM model via single script

**Independent Test**: Run `scripts/install_glm_stem.sh` and verify `ollama list` shows `glm-stem-42exp`

### Implementation for User Story 1

- [x] T008 [P] [US1] Create Bash installation script at scripts/install_glm_stem.sh with:
  - Disk space check (20GB minimum)
  - Ollama availability check
  - HuggingFace download via huggingface_hub or curl
  - Modelfile creation with GLM-optimized parameters
  - ollama create command
  - Verification test
- [x] T009 [P] [US1] Create PowerShell installation script at scripts/install_glm_stem.ps1 with same features
- [x] T010 [US1] Add --variant flag to scripts for Q4_K_M vs Q8_0 selection
- [x] T011 [US1] Add --reinstall flag to scripts for forcing reinstallation
- [x] T012 [US1] Add resume support for interrupted downloads in scripts

**Checkpoint**: ✅ Model can be installed on Linux/macOS/Windows

---

## Phase 4: User Story 2 - Automatic Model Usage (Priority: P2)

**Goal**: MITS automatically uses pruned model with fallback support

**Independent Test**: Start MITS and check logs for "llm_client_initialized model=glm-stem-42exp"

### Implementation for User Story 2

- [x] T013 [US2] Add model availability check in src/models/llm_client.py __init__
- [x] T014 [US2] Implement fallback logic with warning log when glm-stem-42exp unavailable
- [ ] T015 [US2] Test fallback by temporarily renaming model in Ollama

**Checkpoint**: ✅ MITS uses pruned model automatically, falls back gracefully

---

## Phase 5: User Story 3 - Quality Testing (Priority: P3)

**Goal**: Developers can verify model works correctly for STEM tasks

**Independent Test**: Run `pytest tests/test_glm_stem.py -v` and verify >90% pass rate

### Implementation for User Story 3

- [x] T016 [P] [US3] Create test file at tests/test_glm_stem.py with pytest structure
- [x] T017 [P] [US3] Add Ollama fixture for model loading with timeout
- [x] T018 [US3] Implement 5 algebra test cases (linear equations, quadratics)
- [x] T019 [US3] Implement 3 calculus test cases (derivatives, integrals)
- [x] T020 [US3] Implement 5 programming test cases (Python syntax, algorithms)
- [x] T021 [US3] Implement 4 physics test cases (mechanics, formulas)
- [x] T022 [US3] Implement 3 Russian language test cases (bilingual capability)
- [x] T023 [US3] Add pytest-timeout to requirements.txt for test timeouts

**Checkpoint**: ✅ Full test suite validates model quality across STEM domains

---

## Phase 6: Polish & Documentation

**Purpose**: Final documentation and cleanup

- [x] T024 [P] Update README.md with model installation instructions
- [x] T025 [P] Add VRAM usage note to docs/ (if exists) or README.md
- [ ] T026 Run quickstart.md validation end-to-end
- [ ] T027 Verify all existing tests still pass with new default model

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: ✅ Complete
- **Foundational (Phase 2)**: ✅ Complete
- **User Story 1 (Phase 3)**: ✅ Complete
- **User Story 2 (Phase 4)**: ✅ Complete (T015 manual test pending)
- **User Story 3 (Phase 5)**: ✅ Complete
- **Polish (Phase 6)**: 🔄 In progress (2/4 done)

### User Story Dependencies

- **US1 (Installation)**: ✅ Complete
- **US2 (Auto-usage)**: ✅ Complete
- **US3 (Testing)**: ✅ Complete

---

## Summary

| Phase | Tasks | Completed | Status |
|-------|-------|-----------|--------|
| Setup | 2 | 2 | ✅ |
| Foundational | 5 | 5 | ✅ |
| US1: Installation | 5 | 5 | ✅ |
| US2: Auto-usage | 3 | 2 | 🔄 |
| US3: Testing | 8 | 8 | ✅ |
| Polish | 4 | 2 | 🔄 |
| **Total** | **27** | **24** | **89%** |

**MVP Status**: ✅ Complete - Model can be installed and used.
