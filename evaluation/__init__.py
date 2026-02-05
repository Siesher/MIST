"""
Модуль оценки качества MITS.

Содержит метрики и инструменты для оценки качества
ответов сократического репетитора.
"""

from .metrics import (
    TutorEvaluator,
    EvaluationResult,
    ResponseMetrics,
    compare_models,
    print_comparison
)

__all__ = [
    'TutorEvaluator',
    'EvaluationResult',
    'ResponseMetrics',
    'compare_models',
    'print_comparison'
]
