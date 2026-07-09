#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Language Detector для MITS.

Определяет язык текста и математическую нотацию для локализации ответов.

Поддерживает:
- Русский / English определение
- Определение русской vs английской математической нотации
- Unicode детекция кириллицы

T050: Language Detection Utility
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported languages."""
    RUSSIAN = "ru"
    ENGLISH = "en"
    UNKNOWN = "unknown"


class MathNotation(Enum):
    """Mathematical notation style."""
    RUSSIAN = "russian"    # tg, ctg, lg
    ENGLISH = "english"    # tan, cot, log
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class LanguageDetectionResult:
    """Result of language detection."""
    language: Language
    confidence: float  # 0.0 to 1.0
    math_notation: MathNotation
    cyrillic_ratio: float
    has_russian_math: bool
    has_english_math: bool


# === Patterns ===

# Cyrillic Unicode range
CYRILLIC_PATTERN = re.compile(r'[\u0400-\u04FF]')

# Russian-specific math functions
RUSSIAN_MATH_PATTERNS = [
    r'\btg\b',      # tangent
    r'\bctg\b',     # cotangent
    r'\blg\b',      # log base 10
    r'\bsh\b',      # sinh
    r'\bch\b',      # cosh
    r'\bth\b',      # tanh
    r'\bcth\b',     # coth
    r'\barctg\b',   # arctangent
    r'\barcctg\b',  # arccotangent
    r'\bcosec\b',   # cosecant
]

# English-specific math functions
ENGLISH_MATH_PATTERNS = [
    r'\btan\b',
    r'\bcot\b',
    r'\blog\b',     # Often log base 10 or natural
    r'\bsinh\b',
    r'\bcosh\b',
    r'\btanh\b',
    r'\bcoth\b',
    r'\barctan\b',
    r'\barccot\b',
    r'\bcsc\b',
]

# Common Russian words (for content detection, not just alphabet)
RUSSIAN_WORD_PATTERNS = [
    r'\bи\b', r'\bили\b', r'\bнет\b', r'\bда\b',
    r'\bчто\b', r'\bкак\b', r'\bгде\b', r'\bкогда\b',
    r'\bэто\b', r'\bтот\b', r'\bэтот\b',
    r'\bдля\b', r'\bпри\b', r'\bпо\b',
    r'\bесли\b', r'\bкоторый\b', r'\bкакой\b',
    r'\bрешить\b', r'\bнайти\b', r'\bвычислить\b',
    r'\bуравнение\b', r'\bзадача\b', r'\bответ\b',
]

# Common English words
ENGLISH_WORD_PATTERNS = [
    r'\bthe\b', r'\band\b', r'\bor\b', r'\bnot\b',
    r'\bwhat\b', r'\bhow\b', r'\bwhere\b', r'\bwhen\b',
    r'\bthis\b', r'\bthat\b', r'\bwhich\b',
    r'\bfor\b', r'\bwith\b', r'\bfrom\b',
    r'\bif\b', r'\bthen\b', r'\belse\b',
    r'\bsolve\b', r'\bfind\b', r'\bcalculate\b',
    r'\bequation\b', r'\bproblem\b', r'\banswer\b',
]


class LanguageDetector:
    """
    Детектор языка для MITS.

    Определяет:
    - Основной язык текста (ru/en)
    - Стиль математической нотации
    - Уровень уверенности
    """

    def __init__(self, default_language: Language = Language.RUSSIAN):
        """
        Initialize detector.

        Args:
            default_language: Default language when detection is uncertain
        """
        self.default_language = default_language
        self._russian_math_compiled = [
            re.compile(p, re.IGNORECASE) for p in RUSSIAN_MATH_PATTERNS
        ]
        self._english_math_compiled = [
            re.compile(p, re.IGNORECASE) for p in ENGLISH_MATH_PATTERNS
        ]
        self._russian_words_compiled = [
            re.compile(p, re.IGNORECASE | re.UNICODE) for p in RUSSIAN_WORD_PATTERNS
        ]
        self._english_words_compiled = [
            re.compile(p, re.IGNORECASE) for p in ENGLISH_WORD_PATTERNS
        ]

    def detect(self, text: str) -> LanguageDetectionResult:
        """
        Detect language and math notation in text.

        Args:
            text: Input text to analyze

        Returns:
            LanguageDetectionResult with detected language and notation
        """
        if not text or not text.strip():
            return LanguageDetectionResult(
                language=self.default_language,
                confidence=0.0,
                math_notation=MathNotation.UNKNOWN,
                cyrillic_ratio=0.0,
                has_russian_math=False,
                has_english_math=False
            )

        # Calculate cyrillic ratio
        cyrillic_chars = len(CYRILLIC_PATTERN.findall(text))
        alpha_chars = sum(1 for c in text if c.isalpha())
        cyrillic_ratio = cyrillic_chars / max(alpha_chars, 1)

        # Check for math notation
        has_russian_math = any(p.search(text) for p in self._russian_math_compiled)
        has_english_math = any(p.search(text) for p in self._english_math_compiled)

        # Check for language-specific words
        russian_word_count = sum(1 for p in self._russian_words_compiled if p.search(text))
        english_word_count = sum(1 for p in self._english_words_compiled if p.search(text))

        # Determine language
        language, confidence = self._determine_language(
            cyrillic_ratio,
            russian_word_count,
            english_word_count,
            has_russian_math,
            has_english_math
        )

        # Determine math notation
        math_notation = self._determine_notation(has_russian_math, has_english_math)

        return LanguageDetectionResult(
            language=language,
            confidence=confidence,
            math_notation=math_notation,
            cyrillic_ratio=cyrillic_ratio,
            has_russian_math=has_russian_math,
            has_english_math=has_english_math
        )

    def _determine_language(
        self,
        cyrillic_ratio: float,
        russian_words: int,
        english_words: int,
        has_russian_math: bool,
        has_english_math: bool
    ) -> Tuple[Language, float]:
        """Determine language with confidence."""

        # Strong cyrillic presence -> Russian
        if cyrillic_ratio > 0.5:
            confidence = min(0.95, 0.7 + cyrillic_ratio * 0.3)
            return Language.RUSSIAN, confidence

        # Significant cyrillic -> likely Russian
        if cyrillic_ratio > 0.1:
            # Check word patterns too
            if russian_words > english_words:
                confidence = 0.7 + (cyrillic_ratio * 0.2)
                return Language.RUSSIAN, confidence
            elif english_words > russian_words * 2:
                return Language.ENGLISH, 0.6
            else:
                return Language.RUSSIAN, 0.5 + cyrillic_ratio

        # No cyrillic - check words and math
        if cyrillic_ratio < 0.05:
            if english_words > russian_words:
                return Language.ENGLISH, 0.7 + min(0.2, english_words * 0.05)

            # Check math notation as tiebreaker
            if has_russian_math and not has_english_math:
                return Language.RUSSIAN, 0.6
            if has_english_math and not has_russian_math:
                return Language.ENGLISH, 0.6

        # Uncertain - use default
        return self.default_language, 0.4

    def _determine_notation(
        self,
        has_russian_math: bool,
        has_english_math: bool
    ) -> MathNotation:
        """Determine math notation style."""
        if has_russian_math and has_english_math:
            return MathNotation.MIXED
        elif has_russian_math:
            return MathNotation.RUSSIAN
        elif has_english_math:
            return MathNotation.ENGLISH
        else:
            return MathNotation.UNKNOWN

    def is_russian(self, text: str) -> bool:
        """Quick check if text is Russian."""
        result = self.detect(text)
        return result.language == Language.RUSSIAN

    def is_english(self, text: str) -> bool:
        """Quick check if text is English."""
        result = self.detect(text)
        return result.language == Language.ENGLISH

    def should_use_russian_notation(self, text: str) -> bool:
        """Check if Russian math notation should be used."""
        result = self.detect(text)

        # Use Russian notation if:
        # 1. Language is Russian, OR
        # 2. Math notation is explicitly Russian, OR
        # 3. There's significant cyrillic content
        return (
            result.language == Language.RUSSIAN or
            result.math_notation == MathNotation.RUSSIAN or
            result.cyrillic_ratio > 0.2
        )


# Singleton instance
_detector: Optional[LanguageDetector] = None


def get_detector() -> LanguageDetector:
    """Get singleton language detector instance."""
    global _detector
    if _detector is None:
        _detector = LanguageDetector()
    return _detector


def detect_language(text: str) -> LanguageDetectionResult:
    """Convenience function to detect language."""
    return get_detector().detect(text)


def is_russian(text: str) -> bool:
    """Convenience function to check if Russian."""
    return get_detector().is_russian(text)


def is_english(text: str) -> bool:
    """Convenience function to check if English."""
    return get_detector().is_english(text)


def should_use_russian_notation(text: str) -> bool:
    """Convenience function to check notation preference."""
    return get_detector().should_use_russian_notation(text)


# === Example Usage ===

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    detector = LanguageDetector()

    test_cases = [
        "Решите уравнение: $x^2 - 5x + 6 = 0$",
        "Solve the equation: $x^2 - 5x + 6 = 0$",
        "Найдите $\\text{tg}(x)$ если $\\sin(x) = 0.5$",
        "Find $\\tan(x)$ if $\\sin(x) = 0.5$",
        "Вычислите $\\lg(100)$",
        "Calculate $\\log_{10}(100)$",
        "x = 5",  # Ambiguous
        "Привет! Как дела?",
        "Hello! How are you?",
    ]

    print("=== Language Detection Demo ===\n")

    for text in test_cases:
        result = detector.detect(text)
        print(f"Text: {text[:50]}...")
        print(f"  Language: {result.language.value} (confidence: {result.confidence:.2f})")
        print(f"  Notation: {result.math_notation.value}")
        print(f"  Cyrillic: {result.cyrillic_ratio:.2f}")
        print()
