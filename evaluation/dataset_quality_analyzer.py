#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализатор качества датасета MITS.

Оценивает:
- Структурную целостность (JSON, метаданные)
- Педагогическое качество (сократический метод, ходы)
- Лингвистическое качество (русский язык, LaTeX)
- Разнообразие (распределение ходов, дисциплин)
- Обучающую ценность (прогресс, эффективность подсказок)

Использование:
    python evaluation/dataset_quality_analyzer.py \
        --input data/training/nemotron_ready.jsonl \
        --output data/training/quality_report.json
"""

import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class DialogMetrics:
    """Метрики одного диалога."""
    index: int
    turn_count: int
    has_metadata: bool
    
    # Педагогические метрики
    move_distribution: Dict[str, int] = field(default_factory=dict)
    question_ratio: float = 0.0
    tell_ratio: float = 0.0
    encourage_ratio: float = 0.0
    socratic_score: float = 0.0
    
    # Лингвистические метрики
    russian_ratio: float = 0.0
    latex_usage: bool = False
    avg_response_length: float = 0.0
    
    # Обучающие метрики
    has_progression: bool = False
    hint_efficiency: float = 0.0
    student_engagement: float = 0.0
    
    # Итоговая оценка
    overall_quality: float = 0.0
    issues: List[str] = field(default_factory=list)


@dataclass
class DatasetQualityReport:
    """Отчёт о качестве всего датасета."""
    dataset_path: str
    total_dialogs: int
    analyzed_at: str
    
    # Распределение качества
    avg_quality: float
    quality_distribution: Dict[str, int]  # excellent, good, fair, poor
    
    # Составляющие качества
    structural_score: float
    pedagogical_score: float
    linguistic_score: float
    diversity_score: float
    learning_score: float
    
    # Статистика
    move_distribution: Dict[str, float]
    discipline_distribution: Dict[str, int]
    difficulty_distribution: Dict[str, int]
    persona_distribution: Dict[str, int]
    
    # Проблемы
    common_issues: List[Tuple[str, int]]  # (issue, count)
    
    # Рекомендации
    recommendations: List[str]
    
    # Детальные метрики
    dialog_metrics: List[DialogMetrics] = field(default_factory=list)


class DatasetQualityAnalyzer:
    """
    Комплексный анализатор качества датасета.
    
    Проверяет:
    1. Структурную целостность (JSON, метаданные)
    2. Педагогическое качество (сократический метод, ходы)
    3. Лингвистическое качество (русский язык, LaTeX)
    4. Разнообразие (распределение ходов, дисциплин)
    5. Обучающую ценность (прогресс, эффективность подсказок)
    """
    
    VALID_MOVES = {
        "scaffolding", "problematize", "rectify",
        "encourage", "hint", "tell", "clarify", "summarize"
    }
    
    QUESTION_PATTERNS = [
        r'\?$', r'\?["\']?\s*$', r'\?\s*$',
        r'как ты думаешь', r'что ты думаешь', r'можешь ли ты',
        r'попробуй', r'подумай', r'как считаешь',
        r'что получится', r'какой результат', r'почему'
    ]
    
    ANSWER_LEAK_PATTERNS = [
        r'ответ\s*[:=]\s*', r'правильный ответ',
        r'решение\s*[:=]', r'получаем\s*[:=]',
        r'итого\s*[:=]', r'значит,?\s*x\s*=\s*\d'
    ]
    
    def __init__(self):
        """Инициализация анализатора."""
        self.question_re = [re.compile(p, re.IGNORECASE) for p in self.QUESTION_PATTERNS]
        self.leak_re = [re.compile(p, re.IGNORECASE) for p in self.ANSWER_LEAK_PATTERNS]
        self.cyrillic_re = re.compile(r'[а-яА-ЯёЁ]')
    
    def analyze_dataset(
        self,
        input_path: Path,
        sample_size: Optional[int] = None
    ) -> DatasetQualityReport:
        """
        Анализ всего датасета.
        
        Args:
            input_path: Путь к JSONL файлу
            sample_size: Размер выборки (None = все)
        
        Returns:
            DatasetQualityReport с результатами
        """
        logger.info(f"Анализ датасета: {input_path}")
        
        dialog_metrics = []
        issues_counter = Counter()
        
        # Чтение и анализ
        with open(input_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                
                if sample_size and i >= sample_size:
                    break
                
                try:
                    dialog = json.loads(line)
                    metrics = self._analyze_dialog(dialog, i)
                    dialog_metrics.append(metrics)
                    
                    for issue in metrics.issues:
                        issues_counter[issue] += 1
                        
                except Exception as e:
                    logger.warning(f"Ошибка в строке {i}: {e}")
                    issues_counter["parse_error"] += 1
        
        # Агрегация результатов
        report = self._aggregate_results(
            dialog_metrics, issues_counter, input_path
        )
        
        return report
    
    def _analyze_dialog(self, dialog: Dict, index: int) -> DialogMetrics:
        """Анализ одного диалога."""
        conversations = dialog.get("conversations", [])
        metadata = dialog.get("metadata", {})
        
        tutor_turns = [m for m in conversations if m.get("role") == "assistant"]
        student_turns = [m for m in conversations if m.get("role") == "user"]
        
        metrics = DialogMetrics(
            index=index,
            turn_count=len(conversations),
            has_metadata=bool(metadata)
        )
        
        # Проверка минимальной длины
        if len(conversations) < 4:
            metrics.issues.append("too_short")
        
        if not tutor_turns:
            metrics.issues.append("no_tutor_turns")
            return metrics
        
        # Анализ ходов репетитора
        move_counts = Counter()
        question_count = 0
        tell_count = 0
        encourage_count = 0
        total_length = 0
        
        for turn in tutor_turns:
            content = turn.get("content", "")
            total_length += len(content)
            
            # Парсинг JSON
            try:
                data = json.loads(content) if content.strip().startswith('{') else {"move": "", "message": content}
                move = data.get("move", "")
                message = data.get("message", content)
                
                if move in self.VALID_MOVES:
                    move_counts[move] += 1
                
                if move == "tell":
                    tell_count += 1
                elif move == "encourage":
                    encourage_count += 1
                
                # Проверка на вопрос
                if self._has_question(message):
                    question_count += 1
                
                # Проверка на утечку ответа
                if self._has_answer_leak(message):
                    metrics.issues.append("answer_leak")
                    
            except json.JSONDecodeError:
                # Не JSON - проверяем как текст
                if self._has_question(content):
                    question_count += 1
                if self._has_answer_leak(content):
                    metrics.issues.append("answer_leak")
        
        metrics.move_distribution = dict(move_counts)
        total_moves = sum(move_counts.values()) or 1
        
        metrics.question_ratio = question_count / total_moves
        metrics.tell_ratio = tell_count / total_moves
        metrics.encourage_ratio = encourage_count / total_moves
        metrics.avg_response_length = total_length / len(tutor_turns)
        
        # Сократический score
        move_diversity = len(move_counts) / len(self.VALID_MOVES)
        metrics.socratic_score = (
            metrics.question_ratio * 0.5 +
            move_diversity * 0.3 +
            (1 - metrics.tell_ratio) * 0.2
        )
        
        if metrics.tell_ratio > 0.3:
            metrics.issues.append("too_many_tells")
        if metrics.question_ratio < 0.3:
            metrics.issues.append("too_few_questions")
        
        # Лингвистический анализ
        all_text = " ".join(m.get("content", "") for m in conversations)
        metrics.russian_ratio = self._calc_russian_ratio(all_text)
        metrics.latex_usage = "$" in all_text or "\\(" in all_text
        
        if metrics.russian_ratio < 0.7:
            metrics.issues.append("not_russian")
        
        # Обучающая ценность
        metrics.has_progression = self._check_progression(conversations)
        metrics.hint_efficiency = self._calc_hint_efficiency(move_counts)
        metrics.student_engagement = self._calc_student_engagement(student_turns)
        
        # Итоговая оценка
        metrics.overall_quality = self._calc_overall_quality(metrics)
        
        return metrics
    
    def _has_question(self, text: str) -> bool:
        """Проверка наличия вопроса."""
        for pattern in self.question_re:
            if pattern.search(text):
                return True
        return False
    
    def _has_answer_leak(self, text: str) -> bool:
        """Проверка на утечку ответа."""
        for pattern in self.leak_re:
            if pattern.search(text):
                return True
        return False
    
    def _calc_russian_ratio(self, text: str) -> float:
        """Расчёт доли русского языка."""
        if not text:
            return 0.0
        cyrillic = len(self.cyrillic_re.findall(text))
        alpha = sum(1 for c in text if c.isalpha())
        return cyrillic / alpha if alpha > 0 else 0.0
    
    def _check_progression(self, conversations: List[Dict]) -> bool:
        """Проверка наличия прогресса."""
        return len(conversations) >= 4
    
    def _calc_hint_efficiency(self, move_counts: Counter) -> float:
        """Эффективность подсказок."""
        hints = move_counts.get("hint", 0)
        tells = move_counts.get("tell", 0)
        total = hints + tells or 1
        return hints / total
    
    def _calc_student_engagement(self, student_turns: List[Dict]) -> float:
        """Вовлечённость ученика."""
        if not student_turns:
            return 0.0
        avg_length = sum(len(m.get("content", "")) for m in student_turns) / len(student_turns)
        return min(1.0, avg_length / 50.0)
    
    def _calc_overall_quality(
        self,
        metrics: DialogMetrics
    ) -> float:
        """Расчёт итогового качества."""
        scores = []
        
        # Структурная целостность
        structural = (metrics.has_metadata + (1 if metrics.turn_count >= 4 else 0)) / 2
        scores.append(structural)
        
        # Педагогическое качество
        scores.append(metrics.socratic_score)
        
        # Лингвистическое качество
        scores.append(metrics.russian_ratio)
        
        # Разнообразие
        diversity = len(metrics.move_distribution) / len(self.VALID_MOVES)
        scores.append(diversity)
        
        # Обучающая ценность
        learning = (metrics.has_progression + metrics.hint_efficiency) / 2
        scores.append(learning)
        
        return sum(scores) / len(scores)
    
    def _aggregate_results(
        self,
        dialog_metrics: List[DialogMetrics],
        issues_counter: Counter,
        dataset_path: Path
    ) -> DatasetQualityReport:
        """Агрегация результатов."""
        if not dialog_metrics:
            return DatasetQualityReport(
                dataset_path=str(dataset_path),
                total_dialogs=0,
                analyzed_at=datetime.now().isoformat()
            )
        
        total = len(dialog_metrics)
        
        # Распределение качества
        quality_dist = {
            "excellent": sum(1 for m in dialog_metrics if m.overall_quality >= 0.8),
            "good": sum(1 for m in dialog_metrics if 0.6 <= m.overall_quality < 0.8),
            "fair": sum(1 for m in dialog_metrics if 0.4 <= m.overall_quality < 0.6),
            "poor": sum(1 for m in dialog_metrics if m.overall_quality < 0.4)
        }
        
        # Составляющие качества
        structural_score = sum(
            (m.has_metadata + (1 if m.turn_count >= 4 else 0)) / 2
            for m in dialog_metrics
        ) / total
        
        pedagogical_score = sum(m.socratic_score for m in dialog_metrics) / total
        linguistic_score = sum(m.russian_ratio for m in dialog_metrics) / total
        diversity_score = sum(
            len(m.move_distribution) / len(self.VALID_MOVES)
            for m in dialog_metrics
        ) / total
        learning_score = sum(
            (m.has_progression + m.hint_efficiency) / 2
            for m in dialog_metrics
        ) / total
        
        # Распределение ходов
        all_moves = Counter()
        for m in dialog_metrics:
            all_moves.update(m.move_distribution)
        
        total_moves = sum(all_moves.values()) or 1
        move_distribution = {k: v/total_moves for k, v in all_moves.items()}
        
        # Рекомендации
        recommendations = self._generate_recommendations(
            quality_dist, move_distribution, issues_counter
        )
        
        return DatasetQualityReport(
            dataset_path=str(dataset_path),
            total_dialogs=total,
            analyzed_at=datetime.now().isoformat(),
            avg_quality=sum(m.overall_quality for m in dialog_metrics) / total,
            quality_distribution=quality_dist,
            structural_score=structural_score,
            pedagogical_score=pedagogical_score,
            linguistic_score=linguistic_score,
            diversity_score=diversity_score,
            learning_score=learning_score,
            move_distribution=move_distribution,
            discipline_distribution={},  # TODO: извлечь из metadata
            difficulty_distribution={},  # TODO: извлечь из metadata
            persona_distribution={},  # TODO: извлечь из metadata
            common_issues=sorted(issues_counter.items(), key=lambda x: -x[1]),
            recommendations=recommendations,
            dialog_metrics=dialog_metrics
        )
    
    def _generate_recommendations(
        self,
        quality_dist: Dict[str, int],
        move_distribution: Dict[str, float],
        issues_counter: Counter
    ) -> List[str]:
        """Генерация рекомендаций."""
        recommendations = []
        
        total = sum(quality_dist.values())
        poor_rate = quality_dist.get("poor", 0) / total if total > 0 else 0
        
        if poor_rate > 0.2:
            recommendations.append(
                f"Слишком много низкокачественных диалогов ({poor_rate:.1%}). "
                "Рассмотрите настройку генератора."
            )
        
        tell_rate = move_distribution.get("tell", 0)
        if tell_rate > 0.1:
            recommendations.append(
                f"Высокая доля прямых объяснений 'tell' ({tell_rate:.1%}). "
                "Уменьшите max_tell_ratio в промпте."
            )
        
        question_rate = 1.0 - tell_rate - move_distribution.get("encourage", 0)
        if question_rate < 0.5:
            recommendations.append(
                f"Недостаточно вопросов ({question_rate:.1%}). "
                "Усильте требование сократического метода."
            )
        
        # Проблемы
        if issues_counter.get("answer_leak", 0) > 0:
            recommendations.append(
                f"Обнаружены утечки ответов ({issues_counter['answer_leak']} случаев). "
                "Добавьте верификатор в пайплайн генерации."
            )
        
        if issues_counter.get("too_short", 0) > 0:
            recommendations.append(
                f"Слишком короткие диалоги ({issues_counter['too_short']} случаев). "
                "Увеличьте min_turns в генераторе."
            )
        
        if not recommendations:
            recommendations.append("Датасет отличного качества! Продолжайте в том же духе.")
        
        return recommendations


def print_report(report: DatasetQualityReport):
    """Вывод отчёта."""
    print("\n" + "=" * 70)
    print("ОТЧЁТ О КАЧЕСТВЕ ДАТАСЕТА MITS")
    print("=" * 70)
    
    print(f"\n📁 Файл: {report.dataset_path}")
    print(f"📊 Диалогов: {report.total_dialogs}")
    print(f"⏰ Анализ: {report.analyzed_at}")
    
    print(f"\n📈 Среднее качество: {report.avg_quality:.3f}")
    
    print("\n📊 Распределение качества:")
    for quality, count in report.quality_distribution.items():
        pct = count / report.total_dialogs * 100 if report.total_dialogs > 0 else 0
        bar = "█" * int(pct / 5)
        print(f"  {quality:12s}: {count:4d} ({pct:5.1f}%) {bar}")
    
    print("\n🎯 Составляющие качества:")
    print(f"  Структурная:     {report.structural_score:.3f}")
    print(f"  Педагогическая:  {report.pedagogical_score:.3f}")
    print(f"  Лингвистическая: {report.linguistic_score:.3f}")
    print(f"  Разнообразие:     {report.diversity_score:.3f}")
    print(f"  Обучающая:       {report.learning_score:.3f}")
    
    print("\n🎭 Распределение ходов:")
    for move, pct in sorted(report.move_distribution.items(), key=lambda x: -x[1]):
        bar = "█" * int(pct * 20)
        print(f"  {move:15s}: {pct:5.1%} {bar}")
    
    if report.common_issues:
        print("\n⚠️  Частые проблемы:")
        print("-" * 70)
        for issue, count in report.common_issues[:10]:
            print(f"  {issue:30s}: {count:4d}")
    
    print("\n💡 Рекомендации:")
    print("-" * 70)
    for i, rec in enumerate(report.recommendations, 1):
        print(f"  {i}. {rec}")
    
    print("\n" + "=" * 70)


def main():
    """CLI для анализа."""
    parser = argparse.ArgumentParser(
        description="Анализ качества датасета MITS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Полный анализ
  python evaluation/dataset_quality_analyzer.py \\
      --input data/training/nemotron_ready.jsonl \\
      --output data/training/quality_report.json

  # Анализ выборки
  python evaluation/dataset_quality_analyzer.py \\
      --input data/training/nemotron_ready.jsonl \\
      --sample 100
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Входной JSONL файл'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Выходной JSON файл с отчётом'
    )
    parser.add_argument(
        '--sample', '-s',
        type=int,
        help='Размер выборки (None = все)'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Файл не найден: {input_path}")
        return 1
    
    # Анализ
    analyzer = DatasetQualityAnalyzer()
    report = analyzer.analyze_dataset(input_path, sample_size=args.sample)
    
    # Вывод отчёта
    print_report(report)
    
    # Сохранение отчёта
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        report_dict = {
            "dataset_path": report.dataset_path,
            "total_dialogs": report.total_dialogs,
            "analyzed_at": report.analyzed_at,
            "avg_quality": report.avg_quality,
            "quality_distribution": report.quality_distribution,
            "scores": {
                "structural": report.structural_score,
                "pedagogical": report.pedagogical_score,
                "linguistic": report.linguistic_score,
                "diversity": report.diversity_score,
                "learning": report.learning_score
            },
            "move_distribution": report.move_distribution,
            "common_issues": report.common_issues,
            "recommendations": report.recommendations
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Отчёт сохранён: {output_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())
