"""
Algorithmic Tasks Collection — Коллекция алгоритмических задач

Файл с определениями всех задач.
"""

from typing import List

from src.data.algo_task_bank import AlgorithmicTask, Category, Difficulty
from src.execution.code_executor import TestCase


def get_easy_tasks() -> List[AlgorithmicTask]:
    """Лёгкие задачи."""
    return [
        # === 1. Two Sum ===
        AlgorithmicTask(
            id="two_sum",
            title="Two Sum",
            title_ru="Два числа с заданной суммой",
            difficulty=Difficulty.EASY,
            category=Category.ARRAYS,
            description_ru="""Дан массив целых чисел `nums` и целое число `target`. 
Найдите два числа в массиве, которые в сумме дают `target`, и выведите их индексы.

Гарантируется, что решение существует и единственно.""",
            input_format="Первая строка: числа массива через пробел.\nВторая строка: целевая сумма.",
            output_format="Два индекса через пробел (0-индексация).",
            examples=[
                {"input": "2 7 11 15\n9", "output": "0 1", "explanation": "nums[0] + nums[1] = 2 + 7 = 9"},
                {"input": "3 2 4\n6", "output": "1 2", "explanation": "nums[1] + nums[2] = 2 + 4 = 6"}
            ],
            test_cases=[
                TestCase("2 7 11 15\n9", "0 1"),
                TestCase("3 2 4\n6", "1 2"),
                TestCase("3 3\n6", "0 1"),
                TestCase("1 5 3 7 2\n9", "1 3", is_hidden=True),
                TestCase("-1 -2 -3 -4 -5\n-8", "2 4", is_hidden=True),
            ],
            constraints=["2 ≤ len(nums) ≤ 10⁴", "-10⁹ ≤ nums[i] ≤ 10⁹"],
            hints=[
                "Попробуйте использовать словарь для хранения уже просмотренных чисел",
                "Для каждого числа x ищите target - x в словаре",
                "Сложность O(n) достижима с хэш-таблицей"
            ],
            solution_code="""nums = list(map(int, input().split()))
target = int(input())
seen = {}
for i, num in enumerate(nums):
    complement = target - num
    if complement in seen:
        print(seen[complement], i)
        break
    seen[num] = i""",
            solution_explanation="Используем хэш-таблицу для поиска за O(1)"
        ),

        # === 2. Palindrome Check ===
        AlgorithmicTask(
            id="palindrome",
            title="Palindrome Check",
            title_ru="Проверка на палиндром",
            difficulty=Difficulty.EASY,
            category=Category.STRINGS,
            description_ru="""Определите, является ли строка палиндромом.
Палиндром читается одинаково слева направо и справа налево.
Учитывайте только буквы и цифры, игнорируйте регистр.""",
            input_format="Одна строка.",
            output_format="YES если палиндром, иначе NO.",
            examples=[
                {"input": "A man a plan a canal Panama", "output": "YES", "explanation": "amanaplanacanalpanama — палиндром"},
                {"input": "hello", "output": "NO", "explanation": "hello ≠ olleh"}
            ],
            test_cases=[
                TestCase("A man a plan a canal Panama", "YES"),
                TestCase("hello", "NO"),
                TestCase("Was it a car or a cat I saw", "YES"),
                TestCase("", "YES"),
                TestCase("a", "YES"),
                TestCase("ab", "NO", is_hidden=True),
                TestCase("Race a Car", "NO", is_hidden=True),
            ],
            constraints=["0 ≤ len(s) ≤ 2·10⁵"],
            hints=[
                "Сначала очистите строку от лишних символов",
                "Приведите к нижнему регистру",
                "Сравните строку с её реверсом"
            ],
            solution_code="""s = input()
cleaned = ''.join(c.lower() for c in s if c.isalnum())
print("YES" if cleaned == cleaned[::-1] else "NO")""",
        ),

        # === 3. FizzBuzz ===
        AlgorithmicTask(
            id="fizzbuzz",
            title="FizzBuzz",
            title_ru="FizzBuzz",
            difficulty=Difficulty.EASY,
            category=Category.MATH,
            description_ru="""Выведите числа от 1 до n, но:
- Если число делится на 3, выведите "Fizz"
- Если число делится на 5, выведите "Buzz"  
- Если делится на оба, выведите "FizzBuzz"
- Иначе выведите само число""",
            input_format="Целое число n.",
            output_format="n строк с результатом.",
            examples=[
                {"input": "15", "output": "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz"}
            ],
            test_cases=[
                TestCase("5", "1\n2\nFizz\n4\nBuzz"),
                TestCase("15", "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz"),
                TestCase("1", "1"),
                TestCase("3", "1\n2\nFizz", is_hidden=True),
            ],
            constraints=["1 ≤ n ≤ 10⁴"],
            hints=[
                "Проверяйте делимость на 15 первой (или на 3 И 5)",
                "Используйте оператор % для проверки делимости"
            ],
            solution_code="""n = int(input())
for i in range(1, n + 1):
    if i % 15 == 0:
        print("FizzBuzz")
    elif i % 3 == 0:
        print("Fizz")
    elif i % 5 == 0:
        print("Buzz")
    else:
        print(i)""",
        ),

        # === 4. Reverse Array ===
        AlgorithmicTask(
            id="reverse_array",
            title="Reverse Array",
            title_ru="Переворот массива",
            difficulty=Difficulty.EASY,
            category=Category.ARRAYS,
            description_ru="Разверните массив в обратном порядке.",
            input_format="Числа массива через пробел.",
            output_format="Числа в обратном порядке через пробел.",
            examples=[
                {"input": "1 2 3 4 5", "output": "5 4 3 2 1"},
                {"input": "7", "output": "7"}
            ],
            test_cases=[
                TestCase("1 2 3 4 5", "5 4 3 2 1"),
                TestCase("7", "7"),
                TestCase("1 2", "2 1"),
                TestCase("-1 0 1", "1 0 -1", is_hidden=True),
            ],
            hints=["Используйте срез [::-1] или функцию reversed()"],
            solution_code="""arr = list(map(int, input().split()))
print(*arr[::-1])""",
        ),

        # === 5. Count Vowels ===
        AlgorithmicTask(
            id="count_vowels",
            title="Count Vowels",
            title_ru="Подсчёт гласных",
            difficulty=Difficulty.EASY,
            category=Category.STRINGS,
            description_ru="Подсчитайте количество гласных букв (a, e, i, o, u) в строке. Регистр не важен.",
            input_format="Строка.",
            output_format="Количество гласных.",
            examples=[
                {"input": "Hello World", "output": "3", "explanation": "e, o, o"},
                {"input": "Python", "output": "1"}
            ],
            test_cases=[
                TestCase("Hello World", "3"),
                TestCase("Python", "1"),
                TestCase("AEIOU", "5"),
                TestCase("xyz", "0"),
                TestCase("Programming is fun", "5", is_hidden=True),
            ],
            hints=["Используйте множество гласных и метод lower()"],
            solution_code="""s = input().lower()
vowels = set('aeiou')
print(sum(1 for c in s if c in vowels))""",
        ),

        # === 6. Find Maximum ===
        AlgorithmicTask(
            id="find_max",
            title="Find Maximum",
            title_ru="Найти максимум",
            difficulty=Difficulty.EASY,
            category=Category.ARRAYS,
            description_ru="Найдите максимальный элемент в массиве без использования встроенной функции max().",
            input_format="Числа массива через пробел.",
            output_format="Максимальный элемент.",
            examples=[
                {"input": "3 1 4 1 5 9 2 6", "output": "9"},
                {"input": "-5 -2 -8", "output": "-2"}
            ],
            test_cases=[
                TestCase("3 1 4 1 5 9 2 6", "9"),
                TestCase("-5 -2 -8", "-2"),
                TestCase("42", "42"),
                TestCase("0 0 0", "0", is_hidden=True),
            ],
            hints=["Инициализируйте максимум первым элементом и пройдите по массиву"],
            solution_code="""arr = list(map(int, input().split()))
maximum = arr[0]
for num in arr[1:]:
    if num > maximum:
        maximum = num
print(maximum)""",
        ),

        # === 7. Sum of Digits ===
        AlgorithmicTask(
            id="digit_sum",
            title="Sum of Digits",
            title_ru="Сумма цифр",
            difficulty=Difficulty.EASY,
            category=Category.MATH,
            description_ru="Найдите сумму цифр положительного целого числа.",
            input_format="Целое положительное число n.",
            output_format="Сумма его цифр.",
            examples=[
                {"input": "12345", "output": "15", "explanation": "1+2+3+4+5=15"},
                {"input": "999", "output": "27"}
            ],
            test_cases=[
                TestCase("12345", "15"),
                TestCase("999", "27"),
                TestCase("0", "0"),
                TestCase("1000000", "1", is_hidden=True),
            ],
            hints=["Можно работать со строкой или использовать % 10 и // 10"],
            solution_code="""n = input()
print(sum(int(d) for d in n))""",
        ),

        # === 8. Factorial ===
        AlgorithmicTask(
            id="factorial",
            title="Factorial",
            title_ru="Факториал",
            difficulty=Difficulty.EASY,
            category=Category.RECURSION,
            description_ru="Вычислите факториал числа n (n!).",
            input_format="Неотрицательное целое n.",
            output_format="n!",
            examples=[
                {"input": "5", "output": "120", "explanation": "5! = 5×4×3×2×1 = 120"},
                {"input": "0", "output": "1", "explanation": "0! = 1 по определению"}
            ],
            test_cases=[
                TestCase("5", "120"),
                TestCase("0", "1"),
                TestCase("1", "1"),
                TestCase("10", "3628800", is_hidden=True),
                TestCase("20", "2432902008176640000", is_hidden=True),
            ],
            constraints=["0 ≤ n ≤ 20"],
            hints=["Используйте цикл или рекурсию", "Не забудьте базовый случай: 0! = 1"],
            solution_code="""n = int(input())
result = 1
for i in range(2, n + 1):
    result *= i
print(result)""",
        ),

        # === 9. Fibonacci ===
        AlgorithmicTask(
            id="fibonacci",
            title="Fibonacci Number",
            title_ru="Число Фибоначчи",
            difficulty=Difficulty.EASY,
            category=Category.RECURSION,
            description_ru="Найдите n-ое число Фибоначчи. F(0)=0, F(1)=1, F(n)=F(n-1)+F(n-2).",
            input_format="Неотрицательное целое n.",
            output_format="F(n).",
            examples=[
                {"input": "10", "output": "55", "explanation": "0,1,1,2,3,5,8,13,21,34,55"},
                {"input": "0", "output": "0"}
            ],
            test_cases=[
                TestCase("10", "55"),
                TestCase("0", "0"),
                TestCase("1", "1"),
                TestCase("2", "1"),
                TestCase("20", "6765", is_hidden=True),
                TestCase("30", "832040", is_hidden=True),
            ],
            constraints=["0 ≤ n ≤ 30"],
            hints=[
                "Наивная рекурсия будет слишком медленной",
                "Используйте итеративный подход или мемоизацию"
            ],
            solution_code="""n = int(input())
if n <= 1:
    print(n)
else:
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    print(b)""",
        ),

        # === 10. Is Prime ===
        AlgorithmicTask(
            id="is_prime",
            title="Is Prime",
            title_ru="Простое число",
            difficulty=Difficulty.EASY,
            category=Category.MATH,
            description_ru="Определите, является ли число простым.",
            input_format="Целое число n.",
            output_format="YES если простое, иначе NO.",
            examples=[
                {"input": "7", "output": "YES"},
                {"input": "4", "output": "NO", "explanation": "4 = 2 × 2"}
            ],
            test_cases=[
                TestCase("7", "YES"),
                TestCase("4", "NO"),
                TestCase("2", "YES"),
                TestCase("1", "NO"),
                TestCase("0", "NO"),
                TestCase("97", "YES", is_hidden=True),
                TestCase("100", "NO", is_hidden=True),
            ],
            constraints=["0 ≤ n ≤ 10⁶"],
            hints=[
                "Достаточно проверить делители до √n",
                "Числа 0 и 1 не являются простыми"
            ],
            solution_code="""n = int(input())
if n < 2:
    print("NO")
else:
    is_prime = True
    i = 2
    while i * i <= n:
        if n % i == 0:
            is_prime = False
            break
        i += 1
    print("YES" if is_prime else "NO")""",
        ),
    ]


def get_medium_tasks() -> List[AlgorithmicTask]:
    """Средние задачи."""
    return [
        # === 11. Binary Search ===
        AlgorithmicTask(
            id="binary_search",
            title="Binary Search",
            title_ru="Бинарный поиск",
            difficulty=Difficulty.MEDIUM,
            category=Category.SEARCHING,
            description_ru="""Дан отсортированный массив и число x. 
Найдите индекс x в массиве или выведите -1, если его нет.""",
            input_format="Первая строка: отсортированный массив через пробел.\nВторая строка: искомое число.",
            output_format="Индекс числа или -1.",
            examples=[
                {"input": "1 3 5 7 9 11\n7", "output": "3"},
                {"input": "1 2 3\n4", "output": "-1"}
            ],
            test_cases=[
                TestCase("1 3 5 7 9 11\n7", "3"),
                TestCase("1 2 3\n4", "-1"),
                TestCase("1\n1", "0"),
                TestCase("1 2 3 4 5\n1", "0", is_hidden=True),
                TestCase("1 2 3 4 5\n5", "4", is_hidden=True),
            ],
            constraints=["1 ≤ len(arr) ≤ 10⁵", "Массив отсортирован"],
            hints=[
                "Сравнивайте с средним элементом",
                "Сужайте область поиска вдвое на каждом шаге",
                "Сложность должна быть O(log n)"
            ],
            solution_code="""arr = list(map(int, input().split()))
x = int(input())
left, right = 0, len(arr) - 1
result = -1
while left <= right:
    mid = (left + right) // 2
    if arr[mid] == x:
        result = mid
        break
    elif arr[mid] < x:
        left = mid + 1
    else:
        right = mid - 1
print(result)""",
        ),

        # === 12. Merge Sorted Arrays ===
        AlgorithmicTask(
            id="merge_sorted",
            title="Merge Sorted Arrays",
            title_ru="Слияние отсортированных массивов",
            difficulty=Difficulty.MEDIUM,
            category=Category.SORTING,
            description_ru="Слейте два отсортированных массива в один отсортированный.",
            input_format="Первая строка: первый массив.\nВторая строка: второй массив.",
            output_format="Объединённый отсортированный массив.",
            examples=[
                {"input": "1 3 5\n2 4 6", "output": "1 2 3 4 5 6"}
            ],
            test_cases=[
                TestCase("1 3 5\n2 4 6", "1 2 3 4 5 6"),
                TestCase("1 2 3\n4 5 6", "1 2 3 4 5 6"),
                TestCase("1\n2", "1 2"),
                TestCase("5 10 15\n1 2 3 20", "1 2 3 5 10 15 20", is_hidden=True),
            ],
            hints=[
                "Используйте два указателя — по одному на каждый массив",
                "На каждом шаге добавляйте меньший элемент",
                "Не забудьте добавить оставшиеся элементы"
            ],
            solution_code="""a = list(map(int, input().split()))
b = list(map(int, input().split()))
result = []
i = j = 0
while i < len(a) and j < len(b):
    if a[i] <= b[j]:
        result.append(a[i])
        i += 1
    else:
        result.append(b[j])
        j += 1
result.extend(a[i:])
result.extend(b[j:])
print(*result)""",
        ),

        # === 13. Valid Parentheses ===
        AlgorithmicTask(
            id="valid_parens",
            title="Valid Parentheses",
            title_ru="Правильная скобочная последовательность",
            difficulty=Difficulty.MEDIUM,
            category=Category.STACK_QUEUE,
            description_ru="""Проверьте, является ли строка правильной скобочной последовательностью.
Строка содержит только символы '(', ')', '[', ']', '{', '}'.""",
            input_format="Строка со скобками.",
            output_format="YES если правильная, иначе NO.",
            examples=[
                {"input": "()[]{}", "output": "YES"},
                {"input": "([)]", "output": "NO"},
                {"input": "{[]}", "output": "YES"}
            ],
            test_cases=[
                TestCase("()[]{}", "YES"),
                TestCase("([)]", "NO"),
                TestCase("{[]}", "YES"),
                TestCase("(", "NO"),
                TestCase("", "YES"),
                TestCase("((()))", "YES", is_hidden=True),
                TestCase("[({})]", "YES", is_hidden=True),
                TestCase("[", "NO", is_hidden=True),
            ],
            hints=[
                "Используйте стек",
                "При открывающей скобке — добавляйте в стек",
                "При закрывающей — проверяйте и удаляйте из стека"
            ],
            solution_code="""s = input()
stack = []
pairs = {')': '(', ']': '[', '}': '{'}
valid = True
for c in s:
    if c in '([{':
        stack.append(c)
    elif c in ')]}':
        if not stack or stack[-1] != pairs[c]:
            valid = False
            break
        stack.pop()
print("YES" if valid and not stack else "NO")""",
        ),

        # === 14. Anagram Check ===
        AlgorithmicTask(
            id="anagram",
            title="Anagram Check",
            title_ru="Проверка анаграммы",
            difficulty=Difficulty.MEDIUM,
            category=Category.HASH_TABLE,
            description_ru="Проверьте, являются ли две строки анаграммами (содержат одинаковые буквы).",
            input_format="Две строки на отдельных строках.",
            output_format="YES если анаграммы, иначе NO.",
            examples=[
                {"input": "listen\nsilent", "output": "YES"},
                {"input": "hello\nworld", "output": "NO"}
            ],
            test_cases=[
                TestCase("listen\nsilent", "YES"),
                TestCase("hello\nworld", "NO"),
                TestCase("anagram\nnagaram", "YES"),
                TestCase("ab\nba", "YES"),
                TestCase("ab\nab", "YES", is_hidden=True),
                TestCase("aab\nabb", "NO", is_hidden=True),
            ],
            hints=[
                "Сравните отсортированные версии строк",
                "Или используйте Counter для подсчёта букв"
            ],
            solution_code="""s1 = input().lower()
s2 = input().lower()
print("YES" if sorted(s1) == sorted(s2) else "NO")""",
        ),

        # === 15. Longest Substring Without Repeating ===
        AlgorithmicTask(
            id="longest_substring",
            title="Longest Substring Without Repeating",
            title_ru="Наидлиннейшая подстрока без повторов",
            difficulty=Difficulty.MEDIUM,
            category=Category.TWO_POINTERS,
            description_ru="Найдите длину наибольшей подстроки без повторяющихся символов.",
            input_format="Строка.",
            output_format="Длина наибольшей подстроки.",
            examples=[
                {"input": "abcabcbb", "output": "3", "explanation": "'abc'"},
                {"input": "bbbbb", "output": "1"},
                {"input": "pwwkew", "output": "3", "explanation": "'wke'"}
            ],
            test_cases=[
                TestCase("abcabcbb", "3"),
                TestCase("bbbbb", "1"),
                TestCase("pwwkew", "3"),
                TestCase("", "0"),
                TestCase("abcdef", "6", is_hidden=True),
                TestCase("aab", "2", is_hidden=True),
            ],
            hints=[
                "Используйте скользящее окно (два указателя)",
                "Храните символы текущего окна в множестве",
                "При повторе сдвигайте левую границу"
            ],
            solution_code="""s = input()
if not s:
    print(0)
else:
    char_set = set()
    left = max_len = 0
    for right in range(len(s)):
        while s[right] in char_set:
            char_set.remove(s[left])
            left += 1
        char_set.add(s[right])
        max_len = max(max_len, right - left + 1)
    print(max_len)""",
        ),

        # === 16. Group Anagrams ===
        AlgorithmicTask(
            id="group_anagrams",
            title="Group Anagrams",
            title_ru="Группировка анаграмм",
            difficulty=Difficulty.MEDIUM,
            category=Category.HASH_TABLE,
            description_ru="""Сгруппируйте слова-анаграммы вместе.
Выведите группы в порядке их первого появления.""",
            input_format="Слова через пробел.",
            output_format="Группы анаграмм, каждая на новой строке.",
            examples=[
                {"input": "eat tea tan ate nat bat", "output": "eat tea ate\ntan nat\nbat"}
            ],
            test_cases=[
                TestCase("eat tea tan ate nat bat", "eat tea ate\ntan nat\nbat"),
                TestCase("a", "a"),
                TestCase("ab ba cd dc", "ab ba\ncd dc", is_hidden=True),
            ],
            hints=[
                "Ключ группы — отсортированное слово",
                "Используйте defaultdict(list)"
            ],
            solution_code="""from collections import defaultdict
words = input().split()
groups = defaultdict(list)
order = []
for word in words:
    key = ''.join(sorted(word))
    if key not in groups:
        order.append(key)
    groups[key].append(word)
for key in order:
    print(' '.join(groups[key]))""",
        ),

        # === 17. Maximum Subarray (Kadane) ===
        AlgorithmicTask(
            id="max_subarray",
            title="Maximum Subarray",
            title_ru="Максимальная подмассив",
            difficulty=Difficulty.MEDIUM,
            category=Category.DYNAMIC,
            description_ru="Найдите непрерывный подмассив с максимальной суммой.",
            input_format="Массив целых чисел через пробел.",
            output_format="Максимальная сумма подмассива.",
            examples=[
                {"input": "-2 1 -3 4 -1 2 1 -5 4", "output": "6", "explanation": "[4,-1,2,1]"},
                {"input": "1", "output": "1"},
                {"input": "-1 -2 -3", "output": "-1"}
            ],
            test_cases=[
                TestCase("-2 1 -3 4 -1 2 1 -5 4", "6"),
                TestCase("1", "1"),
                TestCase("-1 -2 -3", "-1"),
                TestCase("5 4 -1 7 8", "23", is_hidden=True),
            ],
            hints=[
                "Используйте алгоритм Кадане",
                "Отслеживайте текущую сумму и максимум",
                "Если текущая сумма отрицательна, начните заново"
            ],
            solution_code="""arr = list(map(int, input().split()))
max_sum = current = arr[0]
for num in arr[1:]:
    current = max(num, current + num)
    max_sum = max(max_sum, current)
print(max_sum)""",
        ),

        # === 18. Reverse Linked List (simulation) ===
        AlgorithmicTask(
            id="reverse_list",
            title="Reverse List",
            title_ru="Переворот списка",
            difficulty=Difficulty.MEDIUM,
            category=Category.ARRAYS,
            description_ru="Разверните список, используя O(1) дополнительной памяти.",
            input_format="Числа через пробел.",
            output_format="Числа в обратном порядке.",
            examples=[
                {"input": "1 2 3 4 5", "output": "5 4 3 2 1"}
            ],
            test_cases=[
                TestCase("1 2 3 4 5", "5 4 3 2 1"),
                TestCase("1 2", "2 1"),
                TestCase("1", "1"),
            ],
            hints=["Меняйте элементы местами с двух концов"],
            solution_code="""arr = list(map(int, input().split()))
left, right = 0, len(arr) - 1
while left < right:
    arr[left], arr[right] = arr[right], arr[left]
    left += 1
    right -= 1
print(*arr)""",
        ),

        # === 19. Count Inversions ===
        AlgorithmicTask(
            id="count_inversions",
            title="Count Inversions",
            title_ru="Подсчёт инверсий",
            difficulty=Difficulty.MEDIUM,
            category=Category.SORTING,
            description_ru="""Подсчитайте количество инверсий в массиве.
Инверсия — пара (i, j), где i < j, но arr[i] > arr[j].""",
            input_format="Массив через пробел.",
            output_format="Количество инверсий.",
            examples=[
                {"input": "2 4 1 3 5", "output": "3", "explanation": "(2,1), (4,1), (4,3)"},
                {"input": "1 2 3", "output": "0"}
            ],
            test_cases=[
                TestCase("2 4 1 3 5", "3"),
                TestCase("1 2 3", "0"),
                TestCase("3 2 1", "3"),
                TestCase("1 3 2 4", "1", is_hidden=True),
            ],
            hints=[
                "Наивный алгоритм — O(n²)",
                "Для оптимального решения модифицируйте merge sort"
            ],
            solution_code="""arr = list(map(int, input().split()))
count = 0
for i in range(len(arr)):
    for j in range(i + 1, len(arr)):
        if arr[i] > arr[j]:
            count += 1
print(count)""",
        ),

        # === 20. Unique Paths (DP Grid) ===
        AlgorithmicTask(
            id="unique_paths",
            title="Unique Paths",
            title_ru="Уникальные пути",
            difficulty=Difficulty.MEDIUM,
            category=Category.DYNAMIC,
            description_ru="""Робот стоит в левом верхнем углу сетки m×n.
Он может двигаться только вправо или вниз.
Сколько уникальных путей до правого нижнего угла?""",
            input_format="Два числа: m и n.",
            output_format="Количество путей.",
            examples=[
                {"input": "3 7", "output": "28"},
                {"input": "3 2", "output": "3"}
            ],
            test_cases=[
                TestCase("3 7", "28"),
                TestCase("3 2", "3"),
                TestCase("1 1", "1"),
                TestCase("2 2", "2"),
                TestCase("10 10", "48620", is_hidden=True),
            ],
            hints=[
                "dp[i][j] = dp[i-1][j] + dp[i][j-1]",
                "Первая строка и столбец — все 1",
                "Можно оптимизировать до O(n) памяти"
            ],
            solution_code="""m, n = map(int, input().split())
dp = [1] * n
for i in range(1, m):
    for j in range(1, n):
        dp[j] += dp[j - 1]
print(dp[-1])""",
        ),
    ]


def get_hard_tasks() -> List[AlgorithmicTask]:
    """Сложные задачи."""
    return [
        # === 21. LCS ===
        AlgorithmicTask(
            id="lcs",
            title="Longest Common Subsequence",
            title_ru="Наибольшая общая подпоследовательность",
            difficulty=Difficulty.HARD,
            category=Category.DYNAMIC,
            description_ru="Найдите длину наибольшей общей подпоследовательности двух строк.",
            input_format="Две строки на отдельных строках.",
            output_format="Длина LCS.",
            examples=[
                {"input": "abcde\nace", "output": "3", "explanation": "'ace'"},
                {"input": "abc\nabc", "output": "3"}
            ],
            test_cases=[
                TestCase("abcde\nace", "3"),
                TestCase("abc\nabc", "3"),
                TestCase("abc\ndef", "0"),
                TestCase("abcdgh\naedfhr", "3", is_hidden=True),
            ],
            hints=[
                "Классическая задача ДП",
                "dp[i][j] — LCS для s1[:i] и s2[:j]",
                "Если символы равны: dp[i][j] = dp[i-1][j-1] + 1"
            ],
            solution_code="""s1 = input()
s2 = input()
m, n = len(s1), len(s2)
dp = [[0] * (n + 1) for _ in range(m + 1)]
for i in range(1, m + 1):
    for j in range(1, n + 1):
        if s1[i-1] == s2[j-1]:
            dp[i][j] = dp[i-1][j-1] + 1
        else:
            dp[i][j] = max(dp[i-1][j], dp[i][j-1])
print(dp[m][n])""",
        ),

        # === 22. Edit Distance ===
        AlgorithmicTask(
            id="edit_distance",
            title="Edit Distance",
            title_ru="Редакционное расстояние",
            difficulty=Difficulty.HARD,
            category=Category.DYNAMIC,
            description_ru="""Найдите минимальное количество операций для преобразования s1 в s2.
Допустимые операции: вставка, удаление, замена символа.""",
            input_format="Две строки на отдельных строках.",
            output_format="Минимальное количество операций.",
            examples=[
                {"input": "horse\nros", "output": "3"},
                {"input": "intention\nexecution", "output": "5"}
            ],
            test_cases=[
                TestCase("horse\nros", "3"),
                TestCase("intention\nexecution", "5"),
                TestCase("abc\nabc", "0"),
                TestCase("a\nb", "1", is_hidden=True),
                TestCase("kitten\nsitting", "3", is_hidden=True),
            ],
            hints=[
                "dp[i][j] — расстояние между s1[:i] и s2[:j]",
                "Три операции дают три перехода"
            ],
            solution_code="""s1 = input()
s2 = input()
m, n = len(s1), len(s2)
dp = [[0] * (n + 1) for _ in range(m + 1)]
for i in range(m + 1):
    dp[i][0] = i
for j in range(n + 1):
    dp[0][j] = j
for i in range(1, m + 1):
    for j in range(1, n + 1):
        if s1[i-1] == s2[j-1]:
            dp[i][j] = dp[i-1][j-1]
        else:
            dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
print(dp[m][n])""",
        ),

        # === 23. Knapsack 0/1 ===
        AlgorithmicTask(
            id="knapsack",
            title="0/1 Knapsack",
            title_ru="Рюкзак 0/1",
            difficulty=Difficulty.HARD,
            category=Category.DYNAMIC,
            description_ru="""Дано n предметов с весами и ценностями.
Найдите максимальную ценность, которую можно унести в рюкзаке вместимости W.
Каждый предмет можно взять только один раз.""",
            input_format="Первая строка: n W\nДалее n строк: weight value",
            output_format="Максимальная ценность.",
            examples=[
                {"input": "3 50\n10 60\n20 100\n30 120", "output": "220"}
            ],
            test_cases=[
                TestCase("3 50\n10 60\n20 100\n30 120", "220"),
                TestCase("4 7\n1 1\n3 4\n4 5\n5 7", "9"),
                TestCase("1 1\n2 10", "0", is_hidden=True),
            ],
            hints=[
                "dp[i][w] — максимум для первых i предметов и вместимости w",
                "Для каждого предмета: брать или нет"
            ],
            solution_code="""line = input().split()
n, W = int(line[0]), int(line[1])
items = []
for _ in range(n):
    w, v = map(int, input().split())
    items.append((w, v))
dp = [0] * (W + 1)
for w, v in items:
    for j in range(W, w - 1, -1):
        dp[j] = max(dp[j], dp[j - w] + v)
print(dp[W])""",
        ),

        # === 24. Coin Change ===
        AlgorithmicTask(
            id="coin_change",
            title="Coin Change",
            title_ru="Размен монет",
            difficulty=Difficulty.HARD,
            category=Category.DYNAMIC,
            description_ru="""Дан набор номиналов монет и сумма.
Найдите минимальное количество монет для размена.
Если размен невозможен, выведите -1.""",
            input_format="Первая строка: номиналы монет.\nВторая строка: сумма.",
            output_format="Минимальное количество монет или -1.",
            examples=[
                {"input": "1 2 5\n11", "output": "3", "explanation": "5+5+1"},
                {"input": "2\n3", "output": "-1"}
            ],
            test_cases=[
                TestCase("1 2 5\n11", "3"),
                TestCase("2\n3", "-1"),
                TestCase("1\n0", "0"),
                TestCase("1 5 10 25\n30", "2", is_hidden=True),
            ],
            hints=[
                "dp[i] — минимум монет для суммы i",
                "dp[i] = min(dp[i - coin] + 1) для всех coin"
            ],
            solution_code="""coins = list(map(int, input().split()))
amount = int(input())
dp = [float('inf')] * (amount + 1)
dp[0] = 0
for i in range(1, amount + 1):
    for coin in coins:
        if coin <= i and dp[i - coin] != float('inf'):
            dp[i] = min(dp[i], dp[i - coin] + 1)
print(dp[amount] if dp[amount] != float('inf') else -1)""",
        ),

        # === 25. Word Break ===
        AlgorithmicTask(
            id="word_break",
            title="Word Break",
            title_ru="Разбиение на слова",
            difficulty=Difficulty.HARD,
            category=Category.DYNAMIC,
            description_ru="""Определите, можно ли разбить строку s на слова из словаря.""",
            input_format="Первая строка: строка s.\nВторая строка: слова словаря через пробел.",
            output_format="YES или NO.",
            examples=[
                {"input": "leetcode\nleet code", "output": "YES"},
                {"input": "applepenapple\napple pen", "output": "YES"},
                {"input": "catsandog\ncats dog sand and cat", "output": "NO"}
            ],
            test_cases=[
                TestCase("leetcode\nleet code", "YES"),
                TestCase("applepenapple\napple pen", "YES"),
                TestCase("catsandog\ncats dog sand and cat", "NO"),
                TestCase("a\na", "YES", is_hidden=True),
            ],
            hints=[
                "dp[i] — можно ли разбить s[:i]",
                "Проверяйте все возможные последние слова"
            ],
            solution_code="""s = input()
words = set(input().split())
n = len(s)
dp = [False] * (n + 1)
dp[0] = True
for i in range(1, n + 1):
    for j in range(i):
        if dp[j] and s[j:i] in words:
            dp[i] = True
            break
print("YES" if dp[n] else "NO")""",
        ),

        # === 26. Merge Intervals ===
        AlgorithmicTask(
            id="merge_intervals",
            title="Merge Intervals",
            title_ru="Слияние интервалов",
            difficulty=Difficulty.MEDIUM,
            category=Category.SORTING,
            description_ru="Слейте все пересекающиеся интервалы.",
            input_format="Первая строка: количество интервалов n.\nДалее n строк: start end.",
            output_format="Слитые интервалы, каждый на новой строке.",
            examples=[
                {"input": "4\n1 3\n2 6\n8 10\n15 18", "output": "1 6\n8 10\n15 18"}
            ],
            test_cases=[
                TestCase("4\n1 3\n2 6\n8 10\n15 18", "1 6\n8 10\n15 18"),
                TestCase("2\n1 4\n4 5", "1 5"),
                TestCase("1\n1 1", "1 1", is_hidden=True),
            ],
            hints=[
                "Отсортируйте по началу интервала",
                "Сравнивайте конец предыдущего с началом текущего"
            ],
            solution_code="""n = int(input())
intervals = []
for _ in range(n):
    a, b = map(int, input().split())
    intervals.append([a, b])
intervals.sort()
merged = [intervals[0]]
for start, end in intervals[1:]:
    if start <= merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], end)
    else:
        merged.append([start, end])
for a, b in merged:
    print(a, b)""",
        ),

        # === 27. Quick Sort ===
        AlgorithmicTask(
            id="quicksort",
            title="Quick Sort",
            title_ru="Быстрая сортировка",
            difficulty=Difficulty.MEDIUM,
            category=Category.SORTING,
            description_ru="Отсортируйте массив используя алгоритм быстрой сортировки.",
            input_format="Числа через пробел.",
            output_format="Отсортированные числа.",
            examples=[
                {"input": "3 1 4 1 5 9 2 6", "output": "1 1 2 3 4 5 6 9"}
            ],
            test_cases=[
                TestCase("3 1 4 1 5 9 2 6", "1 1 2 3 4 5 6 9"),
                TestCase("5 4 3 2 1", "1 2 3 4 5"),
                TestCase("1", "1"),
                TestCase("-3 -1 -2", "-3 -2 -1", is_hidden=True),
            ],
            hints=[
                "Выберите опорный элемент (pivot)",
                "Разделите на элементы меньше и больше pivot",
                "Рекурсивно отсортируйте части"
            ],
            solution_code="""def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

arr = list(map(int, input().split()))
print(*quicksort(arr))""",
        ),

        # === 28. Number of Islands (BFS/DFS) ===
        AlgorithmicTask(
            id="num_islands",
            title="Number of Islands",
            title_ru="Количество островов",
            difficulty=Difficulty.HARD,
            category=Category.GRAPHS,
            description_ru="""Дана карта m×n, где 1 — суша, 0 — вода.
Посчитайте количество островов (связных компонент суши).""",
            input_format="Первая строка: m n.\nДалее m строк карты.",
            output_format="Количество островов.",
            examples=[
                {"input": "4 5\n11110\n11010\n11000\n00000", "output": "1"},
                {"input": "4 5\n11000\n11000\n00100\n00011", "output": "3"}
            ],
            test_cases=[
                TestCase("4 5\n11110\n11010\n11000\n00000", "1"),
                TestCase("4 5\n11000\n11000\n00100\n00011", "3"),
                TestCase("1 1\n1", "1"),
                TestCase("1 1\n0", "0", is_hidden=True),
            ],
            hints=[
                "Используйте DFS или BFS",
                "При нахождении '1' запустите обход и пометьте всю компоненту"
            ],
            solution_code="""m, n = map(int, input().split())
grid = [list(input()) for _ in range(m)]

def dfs(i, j):
    if i < 0 or i >= m or j < 0 or j >= n or grid[i][j] != '1':
        return
    grid[i][j] = '0'
    dfs(i+1, j)
    dfs(i-1, j)
    dfs(i, j+1)
    dfs(i, j-1)

count = 0
for i in range(m):
    for j in range(n):
        if grid[i][j] == '1':
            dfs(i, j)
            count += 1
print(count)""",
        ),

        # === 29. Longest Increasing Subsequence ===
        AlgorithmicTask(
            id="lis",
            title="Longest Increasing Subsequence",
            title_ru="Наибольшая возрастающая подпоследовательность",
            difficulty=Difficulty.HARD,
            category=Category.DYNAMIC,
            description_ru="Найдите длину наибольшей строго возрастающей подпоследовательности.",
            input_format="Массив через пробел.",
            output_format="Длина LIS.",
            examples=[
                {"input": "10 9 2 5 3 7 101 18", "output": "4", "explanation": "[2,3,7,101]"},
                {"input": "0 1 0 3 2 3", "output": "4"}
            ],
            test_cases=[
                TestCase("10 9 2 5 3 7 101 18", "4"),
                TestCase("0 1 0 3 2 3", "4"),
                TestCase("7 7 7 7", "1"),
                TestCase("1 2 3 4 5", "5", is_hidden=True),
            ],
            hints=[
                "ДП за O(n²): dp[i] = max(dp[j] + 1) для j < i и arr[j] < arr[i]",
                "Оптимально за O(n log n) с бинарным поиском"
            ],
            solution_code="""arr = list(map(int, input().split()))
n = len(arr)
dp = [1] * n
for i in range(1, n):
    for j in range(i):
        if arr[j] < arr[i]:
            dp[i] = max(dp[i], dp[j] + 1)
print(max(dp))""",
        ),

        # === 30. Median of Sorted Arrays ===
        AlgorithmicTask(
            id="median_sorted",
            title="Median of Two Sorted Arrays",
            title_ru="Медиана двух отсортированных массивов",
            difficulty=Difficulty.HARD,
            category=Category.SEARCHING,
            description_ru="Найдите медиану двух отсортированных массивов.",
            input_format="Два массива на отдельных строках.",
            output_format="Медиана (с точностью до 1 знака после запятой).",
            examples=[
                {"input": "1 3\n2", "output": "2.0"},
                {"input": "1 2\n3 4", "output": "2.5"}
            ],
            test_cases=[
                TestCase("1 3\n2", "2.0"),
                TestCase("1 2\n3 4", "2.5"),
                TestCase("1\n2", "1.5"),
                TestCase("1 2 3\n4 5 6", "3.5", is_hidden=True),
            ],
            hints=[
                "Простое решение: объедините и найдите медиану",
                "Оптимально за O(log(min(m,n))) с бинарным поиском"
            ],
            solution_code="""a = list(map(int, input().split()))
b = list(map(int, input().split()))
merged = sorted(a + b)
n = len(merged)
if n % 2 == 1:
    print(float(merged[n // 2]))
else:
    print((merged[n // 2 - 1] + merged[n // 2]) / 2)""",
        ),
    ]


def get_all_algorithmic_tasks() -> List[AlgorithmicTask]:
    """Получить все задачи."""
    return get_easy_tasks() + get_medium_tasks() + get_hard_tasks()
