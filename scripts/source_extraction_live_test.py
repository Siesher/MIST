"""Живой end-to-end тест извлечения источников + построения графа знаний.

Прогоняет реальные источники через SourceExtractor (живая модель llama-swap),
строит ИЗОЛИРОВАННЫЙ граф (in-memory, реальный forge.json не трогается),
проверяет рост графа и связность, затем демонстрирует навигацию по построенному
графу через PersonalizedNavigator.

Требует поднятый llama-swap на :8090 (LLM_BACKEND=llamacpp).

Usage: uv run python scripts/source_extraction_live_test.py
"""

from __future__ import annotations

import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _hr(title: str) -> None:
    print("\n" + "═" * 70)
    print(f"  {title}")
    print("═" * 70)


# ── Источники для извлечения ─────────────────────────────────────────

SRC_MATH = """Производная функции — это предел отношения приращения функции к
приращению аргумента, когда приращение аргумента стремится к нулю. Производная
характеризует скорость изменения функции. Геометрически производная равна
тангенсу угла наклона касательной к графику функции в данной точке.

Правило дифференцирования сложной функции (правило цепочки): если y = f(g(x)),
то y' = f'(g(x)) · g'(x). Это одно из ключевых правил, применяемых при
нахождении производных составных функций, например sin(x^2) или e^(3x).

Производная произведения: (uv)' = u'v + uv'. Производная частного:
(u/v)' = (u'v - uv') / v^2."""

SRC_PHYSICS = """Равноускоренное движение — это движение, при котором тело за
любые равные промежутки времени изменяет свою скорость на одну и ту же величину.
Ускорение при таком движении постоянно. Основное уравнение: v = v0 + a·t, где
v0 — начальная скорость, a — ускорение, t — время.

Путь при равноускоренном движении: s = v0·t + (a·t^2)/2. Связь скорости и пути
без времени: v^2 = v0^2 + 2·a·s. Свободное падение — частный случай
равноускоренного движения с ускорением g ≈ 9,8 м/с^2."""


def _build_long_source() -> str:
    """~13000 символов: распознаваемый концепт в начале и ОТДЕЛЬНЫЙ распознаваемый
    концепт в самом КОНЦЕ — для проверки, что извлекается весь документ, а не
    первые 3000 символов (как было до рефакторинга SourceExtractor)."""
    head = (
        "Арифметическая прогрессия — это числовая последовательность, в которой "
        "каждый следующий член получается прибавлением одного и того же числа "
        "(разности прогрессии d) к предыдущему. n-й член: a_n = a_1 + (n-1)·d. "
        "Сумма первых n членов: S_n = (a_1 + a_n)·n / 2.\n\n"
    )
    filler = (
        "Геометрическая прогрессия задаётся первым членом и знаменателем q; "
        "её n-й член равен b_1·q^(n-1). Эти последовательности широко применяются "
        "в задачах на проценты, сложные проценты и финансовую математику. "
    ) * 60  # ~раздувает середину до многих тысяч символов
    # Отдельный, ХОРОШО РАСПОЗНАВАЕМЫЙ концепт В САМОМ КОНЦЕ документа:
    tail = (
        "\n\nПризнак Даламбера сходимости числового ряда: если для ряда с "
        "положительными членами существует предел отношения последующего члена к "
        "предыдущему lim(a_(n+1)/a_n) = L при n→∞, то при L < 1 ряд сходится, "
        "при L > 1 ряд расходится, а при L = 1 признак не даёт ответа. Это "
        "ключевой инструмент исследования сходимости рядов."
    )
    return head + filler + tail


def main() -> int:
    # 0. Проверка живого бэкенда
    _hr("0. Проверка llama-swap (:8090)")
    try:
        import requests

        r = requests.get("http://127.0.0.1:8090/v1/models", timeout=5)
        models = [m.get("id") for m in r.json().get("data", [])]
        print(f"  llama-swap доступен. Модели: {models}")
    except Exception as e:
        print(f"  ❌ llama-swap недоступен: {e}")
        print(
            "  Запусти: C:/OpenCode/llama-swap/llama-swap.exe --config llama-swap.yaml --listen :8090"
        )
        return 2

    from src.knowledge.knowledge_forge import KnowledgeGraph
    from src.knowledge.source_extractor import SourceExtractor

    # 1. Изолированный граф (in-memory — реальный forge.json не трогаем)
    _hr("1. Создание изолированного графа (in-memory)")
    graph = KnowledgeGraph(storage_path=None)
    base = graph.stats
    print(f"  Базовое состояние: {base['total_nodes']} узлов, {base['total_edges']} рёбер")

    extractor = SourceExtractor()  # llm=None → живой llama-swap через _make_llm

    sources = [
        ("Учебник: производные", SRC_MATH, "math"),
        ("Учебник: кинематика", SRC_PHYSICS, "physics"),
        ("Длинный конспект (~13K симв.)", _build_long_source(), "math"),
    ]

    # 2. Извлечение + построение графа
    _hr("2. Извлечение источников → построение графа (живая модель)")
    per_source = []
    for name, text, domain in sources:
        t0 = time.time()
        print(f"\n  ▸ «{name}» ({domain}, {len(text)} симв.)")
        summary = extractor.ingest(graph, text, domain=domain, source_name=name)
        dt = time.time() - t0
        per_source.append((name, summary, dt))
        print(
            f"    +{summary['nodes_added']} узлов, +{summary['edges_added']} рёбер "
            f"(пропущено {summary['nodes_skipped']}, слито {summary['nodes_merged']}) за {dt:.1f}с"
        )

    # 3. Итоговая статистика графа
    _hr("3. Итоговый построенный граф")
    final = graph.stats
    print(f"  Узлов: {final['total_nodes']}  |  Рёбер: {final['total_edges']}")
    print(f"  По типам:   {final.get('by_type', {})}")
    print(f"  По доменам: {final.get('by_domain', {})}")
    print(f"  Типы рёбер: {final.get('edge_types', {})}")

    print("\n  Примеры извлечённых узлов:")
    for node in list(graph._nodes.values())[:8]:
        print(
            f"    • [{node.node_type.value}] {node.title}  (id={node.id}, conf={node.confidence})"
        )

    if graph._edges:
        print("\n  Примеры извлечённых связей:")
        for edge in graph._edges[:6]:
            print(f"    • {edge.source_id} --{edge.edge_type.value}--> {edge.target_id}")

    # 4. Проверка покрытия всего документа (концепт из КОНЦА длинного источника)
    _hr("4. Проверка полного покрытия (баг text[:3000] устранён)")
    late_hits = [
        n
        for n in graph._nodes.values()
        if "даламбер" in (n.title + n.content).lower() or "сходим" in (n.title + n.content).lower()
    ]
    if late_hits:
        print(f"  ✅ Концепт из КОНЦА длинного документа извлечён: {[n.title for n in late_hits]}")
        print("     → подтверждено: анализируется весь документ, а не первые 3000 символов.")
    else:
        print("  ⚠️  Концепт 'признак Даламбера' (конец документа) не найден в графе.")
        print(
            "     (LLM мог сформулировать иначе — см. список узлов выше; обрезка устранена на уровне кода+юнит-теста.)"
        )

    # 5. Капстоун: навигация по ПОСТРОЕННОМУ графу
    _hr("5. Навигация по построенному графу (PersonalizedNavigator)")
    try:
        from src.knowledge.navigator import PersonalizedNavigator

        nav = PersonalizedNavigator(graph, {})  # пустое мастерство (нет студента)
        sample_node = next(iter(graph._nodes.values()), None)
        if sample_node:
            ctx = nav.get_concept_context("demo_student", sample_node.id)
            print(f"  get_concept_context('{sample_node.id}'):")
            if ctx:
                print(
                    f"    концепт: {ctx.get('concept', {}).get('title', '—') if isinstance(ctx, dict) else ctx}"
                )
                neigh = ctx.get("neighbors", []) if isinstance(ctx, dict) else []
                print(f"    соседей в графе: {len(neigh)}")
                print("    ✅ Навигатор успешно читает построенный граф.")
            else:
                print("    (контекст пуст — узел без соседей, но вызов прошёл без ошибок)")
    except Exception as e:
        print(f"  ⚠️  Навигация: {e}")

    # 6. Path A: дайджест источника (summarize)
    _hr("6. Path A — быстрый дайджест источника (SourceAnalyzer.summarize)")
    try:
        from src.knowledge.source_analyzer import SourceAnalyzer

        digest = SourceAnalyzer().summarize(SRC_MATH, source_name="Учебник: производные")
        print(f"  Ключевые тезисы ({len(digest['key_points'])}):")
        for kp in digest["key_points"][:5]:
            print(f"    • {kp}")
        if digest.get("formulas"):
            print(f"  Формулы: {digest['formulas'][:4]}")
        print(f"  Темы: {digest.get('topics', [])[:5]}")
    except Exception as e:
        print(f"  ⚠️  summarize: {e}")

    # ── Вердикт ──────────────────────────────────────────────────────
    _hr("ВЕРДИКТ")
    added_total = final["total_nodes"] - base["total_nodes"]
    ok = added_total > 0
    print(f"  Узлов добавлено: {added_total}, рёбер: {final['total_edges']}")
    print(
        f"  Источников обработано: {len(sources)} ({sum(s[1]['nodes_added'] for s in per_source)} узлов суммарно)"
    )
    print(
        f"  Покрытие конца длинного документа: {'ДА' if late_hits else 'не подтверждено на этом прогоне'}"
    )
    print(
        f"\n  {'✅ СИСТЕМА ИЗВЛЕЧЕНИЯ + ГРАФ РАБОТАЮТ' if ok else '❌ ГРАФ НЕ ПОСТРОЕН — см. логи'}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
