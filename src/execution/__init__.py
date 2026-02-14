"""
__init__.py для модуля execution
"""

from src.execution.code_executor import (
    CodeExecutor,
    ExecutionResult,
    SubmissionResult,
    TestCase,
    ExecutionStatus,
    ErrorAnalyzer,
    CodeSecurityChecker
)

from src.execution.code_analyzer import (
    CodeAnalyzer,
    CodeIssue,
    IssueLevel,
    ComplexityAnalysis,
    CodeMetrics,
    SolutionComparer
)

__all__ = [
    # Executor
    'CodeExecutor',
    'ExecutionResult', 
    'SubmissionResult',
    'TestCase',
    'ExecutionStatus',
    'ErrorAnalyzer',
    'CodeSecurityChecker',
    # Analyzer
    'CodeAnalyzer',
    'CodeIssue',
    'IssueLevel',
    'ComplexityAnalysis',
    'CodeMetrics',
    'SolutionComparer'
]
