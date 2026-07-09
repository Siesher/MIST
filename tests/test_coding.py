"""
Тест системы программирования MITS
"""

import os
import sys

# Настройка кодировки для Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, '.')

def test_code_executor():
    """Тест исполнителя кода."""
    print("=" * 50)
    print("🧪 Тест Code Executor")
    print("=" * 50)

    from src.execution.code_executor import CodeExecutor, TestCase

    executor = CodeExecutor(timeout_seconds=5.0)

    # Тест 1: Простой код
    code = """
n = int(input())
print(n * 2)
"""
    result = executor.execute(code, "5")
    print(f"\n✅ Тест 1 (простой код): {result.status.value}")
    print(f"   Вывод: {result.output}")
    assert result.output == "10", f"Ожидалось 10, получено {result.output}"

    # Тест 2: Ошибка выполнения
    code_error = """
x = 1 / 0
"""
    result = executor.execute(code_error)
    print(f"\n✅ Тест 2 (ошибка): {result.status.value}")
    assert result.status.value == "runtime_error"

    # Тест 3: Тайм-аут
    code_timeout = """
while True:
    pass
"""
    result = executor.execute(code_timeout, timeout=1.0)
    print(f"\n✅ Тест 3 (тайм-аут): {result.status.value}")
    assert result.status.value == "time_limit"

    # Тест 4: Запуск на тестах
    code_sum = """
a, b = map(int, input().split())
print(a + b)
"""
    tests = [
        TestCase("1 2", "3"),
        TestCase("10 20", "30"),
        TestCase("-5 5", "0"),
    ]
    result = executor.run_tests(code_sum, tests)
    print(f"\n✅ Тест 4 (набор тестов): {result.passed}/{result.total}")
    assert result.is_accepted

    # Тест 5: Безопасность
    code_unsafe = """
import os
os.system('ls')
"""
    result = executor.execute(code_unsafe)
    print(f"\n✅ Тест 5 (безопасность): {result.status.value}")
    assert result.status.value == "security_error"

    print("\n✅ Code Executor: ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    return True


def test_code_analyzer():
    """Тест анализатора кода."""
    print("\n" + "=" * 50)
    print("🧪 Тест Code Analyzer")
    print("=" * 50)

    from src.execution.code_analyzer import CodeAnalyzer

    analyzer = CodeAnalyzer()

    # Тест 1: Простой код
    code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

print(factorial(5))
"""
    result = analyzer.analyze(code)
    print("\n✅ Тест 1 (рекурсия):")
    print(f"   Сложность: {result['complexity'].time_complexity}")
    print(f"   Рекурсия: {result['complexity'].has_recursion}")
    assert result['complexity'].has_recursion

    # Тест 2: Вложенные циклы
    code_nested = """
for i in range(n):
    for j in range(n):
        for k in range(n):
            print(i, j, k)
"""
    result = analyzer.analyze(code_nested)
    print("\n✅ Тест 2 (вложенные циклы):")
    print(f"   Сложность: {result['complexity'].time_complexity}")
    print(f"   Глубина: {result['complexity'].loop_depth}")
    assert result['complexity'].loop_depth == 3

    # Тест 3: Антипаттерны
    code_bad = """
for i in range(len(lst)):
    if x == True:
        pass
"""
    result = analyzer.analyze(code_bad)
    print("\n✅ Тест 3 (антипаттерны):")
    print(f"   Найдено проблем: {len(result['issues'])}")
    assert len(result['issues']) >= 2

    print("\n✅ Code Analyzer: ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    return True


def test_task_bank():
    """Тест банка задач."""
    print("\n" + "=" * 50)
    print("🧪 Тест Task Bank")
    print("=" * 50)

    from src.data.algo_task_bank import AlgorithmicTaskBank, Difficulty

    # Удаляем старый файл если есть
    bank_path = "./data/algo_tasks.json"
    if os.path.exists(bank_path):
        os.remove(bank_path)

    bank = AlgorithmicTaskBank()

    stats = bank.get_stats()
    print(f"\n✅ Загружено задач: {stats['total']}")
    print(f"   Easy: {stats['by_difficulty']['easy']}")
    print(f"   Medium: {stats['by_difficulty']['medium']}")
    print(f"   Hard: {stats['by_difficulty']['hard']}")

    assert stats['total'] >= 30, f"Ожидалось >=30 задач, получено {stats['total']}"

    # Тест получения задачи
    task = bank.get_task("two_sum")
    assert task is not None, "Задача two_sum не найдена"
    print("\n✅ Задача two_sum:")
    print(f"   Название: {task.title_ru}")
    print(f"   Тестов: {len(task.test_cases)}")

    # Тест случайной задачи
    random_task = bank.get_random_task(difficulty=Difficulty.EASY)
    assert random_task is not None
    print(f"\n✅ Случайная задача: {random_task.title_ru}")

    print("\n✅ Task Bank: ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    return True


def test_full_workflow():
    """Тест полного рабочего процесса."""
    print("\n" + "=" * 50)
    print("🧪 Тест полного workflow")
    print("=" * 50)

    from src.data.algo_task_bank import AlgorithmicTaskBank
    from src.execution.code_analyzer import CodeAnalyzer
    from src.execution.code_executor import CodeExecutor

    # 1. Загружаем банк
    bank = AlgorithmicTaskBank()

    # 2. Получаем задачу
    task = bank.get_task("fibonacci")
    print(f"\n📋 Задача: {task.title_ru}")

    # 3. Решение студента
    student_code = """
n = int(input())
if n <= 1:
    print(n)
else:
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    print(b)
"""

    # 4. Анализ кода
    analyzer = CodeAnalyzer()
    analysis = analyzer.analyze(student_code)
    print("\n📊 Анализ кода:")
    print(f"   Сложность: {analysis['complexity'].time_complexity}")
    print(f"   Проблем: {len(analysis['issues'])}")

    # 5. Запуск на тестах
    executor = CodeExecutor()
    result = executor.run_tests(student_code, task.test_cases)

    print(f"\n🧪 Результаты тестов: {result.passed}/{result.total}")

    if result.is_accepted:
        print("\n🎉 ACCEPTED!")
    else:
        print(f"\n❌ Ошибка: {result.status.value}")
        if result.first_failed:
            print(f"   Тест {result.first_failed.test_number}")

    assert result.is_accepted, "Решение должно быть принято"

    print("\n✅ Full Workflow: ТЕСТ ПРОЙДЕН")
    return True


def main():
    """Запуск всех тестов."""
    print("\n" + "=" * 60)
    print("🐝 MITS — Тестирование системы программирования")
    print("=" * 60)

    tests = [
        ("Code Executor", test_code_executor),
        ("Code Analyzer", test_code_analyzer),
        ("Task Bank", test_task_bank),
        ("Full Workflow", test_full_workflow),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {name}: ОШИБКА")
            print(f"   {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"📊 ИТОГО: {passed}/{len(tests)} тестов пройдено")

    if failed == 0:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print(f"❌ {failed} тестов провалено")

    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
