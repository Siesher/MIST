"""
Дополнительные алгоритмические задачи (часть 2)
"""

from typing import List

from src.data.algo_task_bank import AlgorithmicTask, Category, Difficulty
from src.execution.code_executor import TestCase


def get_additional_easy_tasks() -> List[AlgorithmicTask]:
    """Дополнительные лёгкие задачи."""
    return [
        AlgorithmicTask(
            id="even_odd",
            title="Even or Odd",
            title_ru="Чётное или нечётное",
            difficulty=Difficulty.EASY,
            category=Category.MATH,
            description_ru="Определите, является ли число чётным или нечётным.",
            input_format="Целое число n.",
            output_format="EVEN если чётное, ODD если нечётное.",
            examples=[{"input": "4", "output": "EVEN"}, {"input": "7", "output": "ODD"}],
            test_cases=[
                TestCase("4", "EVEN"), TestCase("7", "ODD"),
                TestCase("0", "EVEN"), TestCase("-3", "ODD", is_hidden=True),
            ],
            hints=["Используйте оператор % для проверки остатка от деления на 2"],
            solution_code='n = int(input())\nprint("EVEN" if n % 2 == 0 else "ODD")',
        ),

        AlgorithmicTask(
            id="min_max",
            title="Min and Max",
            title_ru="Минимум и максимум",
            difficulty=Difficulty.EASY,
            category=Category.ARRAYS,
            description_ru="Найдите минимальный и максимальный элементы массива.",
            input_format="Числа через пробел.",
            output_format="Минимум и максимум через пробел.",
            examples=[{"input": "3 1 4 1 5 9", "output": "1 9"}],
            test_cases=[
                TestCase("3 1 4 1 5 9", "1 9"),
                TestCase("5", "5 5"),
                TestCase("-1 -5 -3", "-5 -1", is_hidden=True),
            ],
            hints=["Можно использовать min() и max() или один проход"],
            solution_code='arr = list(map(int, input().split()))\nprint(min(arr), max(arr))',
        ),

        AlgorithmicTask(
            id="count_words",
            title="Count Words",
            title_ru="Подсчёт слов",
            difficulty=Difficulty.EASY,
            category=Category.STRINGS,
            description_ru="Подсчитайте количество слов в строке.",
            input_format="Строка.",
            output_format="Количество слов.",
            examples=[{"input": "Hello World", "output": "2"}],
            test_cases=[
                TestCase("Hello World", "2"),
                TestCase("One", "1"),
                TestCase("   multiple   spaces   here   ", "3", is_hidden=True),
            ],
            hints=["Метод split() разбивает строку по пробелам"],
            solution_code='s = input()\nprint(len(s.split()))',
        ),

        AlgorithmicTask(
            id="gcd",
            title="GCD",
            title_ru="НОД двух чисел",
            difficulty=Difficulty.EASY,
            category=Category.MATH,
            description_ru="Найдите наибольший общий делитель двух чисел.",
            input_format="Два числа a и b через пробел.",
            output_format="НОД(a, b).",
            examples=[{"input": "12 18", "output": "6"}, {"input": "7 13", "output": "1"}],
            test_cases=[
                TestCase("12 18", "6"), TestCase("7 13", "1"),
                TestCase("100 100", "100"), TestCase("1 1000", "1", is_hidden=True),
            ],
            hints=["Используйте алгоритм Евклида: gcd(a, b) = gcd(b, a % b)"],
            solution_code='a, b = map(int, input().split())\nwhile b:\n    a, b = b, a % b\nprint(a)',
        ),

        AlgorithmicTask(
            id="remove_duplicates",
            title="Remove Duplicates",
            title_ru="Удаление дубликатов",
            difficulty=Difficulty.EASY,
            category=Category.ARRAYS,
            description_ru="Удалите дубликаты из массива, сохранив порядок первого вхождения.",
            input_format="Числа через пробел.",
            output_format="Уникальные числа в порядке первого появления.",
            examples=[{"input": "1 2 2 3 1 4", "output": "1 2 3 4"}],
            test_cases=[
                TestCase("1 2 2 3 1 4", "1 2 3 4"),
                TestCase("1 1 1", "1"),
                TestCase("1 2 3", "1 2 3", is_hidden=True),
            ],
            hints=["Используйте множество для отслеживания виденных элементов"],
            solution_code='arr = list(map(int, input().split()))\nseen = set()\nresult = []\nfor x in arr:\n    if x not in seen:\n        seen.add(x)\n        result.append(x)\nprint(*result)',
        ),

        AlgorithmicTask(
            id="power_of_two",
            title="Power of Two",
            title_ru="Степень двойки",
            difficulty=Difficulty.EASY,
            category=Category.MATH,
            description_ru="Определите, является ли число степенью двойки.",
            input_format="Целое положительное число n.",
            output_format="YES или NO.",
            examples=[{"input": "16", "output": "YES"}, {"input": "18", "output": "NO"}],
            test_cases=[
                TestCase("16", "YES"), TestCase("18", "NO"),
                TestCase("1", "YES"), TestCase("1024", "YES", is_hidden=True),
            ],
            hints=["n & (n-1) == 0 для степеней двойки", "Или делите на 2 пока можно"],
            solution_code='n = int(input())\nprint("YES" if n > 0 and (n & (n - 1)) == 0 else "NO")',
        ),

        AlgorithmicTask(
            id="array_sum",
            title="Array Sum",
            title_ru="Сумма массива",
            difficulty=Difficulty.EASY,
            category=Category.ARRAYS,
            description_ru="Найдите сумму всех элементов массива.",
            input_format="Числа через пробел.",
            output_format="Сумма.",
            examples=[{"input": "1 2 3 4 5", "output": "15"}],
            test_cases=[
                TestCase("1 2 3 4 5", "15"),
                TestCase("0", "0"),
                TestCase("-1 1 -2 2", "0", is_hidden=True),
            ],
            hints=["Используйте sum() или цикл"],
            solution_code='arr = list(map(int, input().split()))\nprint(sum(arr))',
        ),

        AlgorithmicTask(
            id="second_largest",
            title="Second Largest",
            title_ru="Второй максимум",
            difficulty=Difficulty.EASY,
            category=Category.ARRAYS,
            description_ru="Найдите второй по величине элемент массива.",
            input_format="Числа через пробел (минимум 2 различных).",
            output_format="Второй максимум.",
            examples=[{"input": "1 2 3 4 5", "output": "4"}, {"input": "5 5 4 4 3", "output": "4"}],
            test_cases=[
                TestCase("1 2 3 4 5", "4"),
                TestCase("5 5 4 4 3", "4"),
                TestCase("1 2", "1", is_hidden=True),
            ],
            hints=["Отсортируйте и найдите уникальные значения"],
            solution_code='arr = list(map(int, input().split()))\nunique = sorted(set(arr), reverse=True)\nprint(unique[1])',
        ),
    ]


def get_additional_medium_tasks() -> List[AlgorithmicTask]:
    """Дополнительные средние задачи."""
    return [
        AlgorithmicTask(
            id="rotate_array",
            title="Rotate Array",
            title_ru="Циклический сдвиг",
            difficulty=Difficulty.MEDIUM,
            category=Category.ARRAYS,
            description_ru="Сдвиньте массив вправо на k позиций.",
            input_format="Первая строка: массив. Вторая строка: k.",
            output_format="Сдвинутый массив.",
            examples=[{"input": "1 2 3 4 5\n2", "output": "4 5 1 2 3"}],
            test_cases=[
                TestCase("1 2 3 4 5\n2", "4 5 1 2 3"),
                TestCase("1 2 3\n3", "1 2 3"),
                TestCase("1 2\n5", "2 1", is_hidden=True),
            ],
            hints=["k = k % len(arr)", "Используйте срезы: arr[-k:] + arr[:-k]"],
            solution_code='arr = list(map(int, input().split()))\nk = int(input()) % len(arr)\nresult = arr[-k:] + arr[:-k]\nprint(*result)',
        ),

        AlgorithmicTask(
            id="majority_element",
            title="Majority Element",
            title_ru="Элемент большинства",
            difficulty=Difficulty.MEDIUM,
            category=Category.ARRAYS,
            description_ru="Найдите элемент, который встречается более n/2 раз.",
            input_format="Массив через пробел.",
            output_format="Элемент большинства.",
            examples=[{"input": "3 2 3", "output": "3"}, {"input": "2 2 1 1 1 2 2", "output": "2"}],
            test_cases=[
                TestCase("3 2 3", "3"),
                TestCase("2 2 1 1 1 2 2", "2"),
                TestCase("1", "1", is_hidden=True),
            ],
            hints=["Алгоритм Бойера-Мура", "Или Counter и проверка"],
            solution_code='from collections import Counter\narr = list(map(int, input().split()))\nc = Counter(arr)\nprint(c.most_common(1)[0][0])',
        ),

        AlgorithmicTask(
            id="product_except_self",
            title="Product Except Self",
            title_ru="Произведение кроме себя",
            difficulty=Difficulty.MEDIUM,
            category=Category.ARRAYS,
            description_ru="Для каждого элемента вычислите произведение всех остальных элементов.",
            input_format="Массив через пробел.",
            output_format="Массив произведений.",
            examples=[{"input": "1 2 3 4", "output": "24 12 8 6"}],
            test_cases=[
                TestCase("1 2 3 4", "24 12 8 6"),
                TestCase("2 3", "3 2"),
                TestCase("-1 1 0 -3 3", "0 0 9 0 0", is_hidden=True),
            ],
            hints=["Два прохода: слева направо и справа налево", "Или используйте деление (осторожно с нулями)"],
            solution_code='arr = list(map(int, input().split()))\nn = len(arr)\nresult = [1] * n\nleft = 1\nfor i in range(n):\n    result[i] = left\n    left *= arr[i]\nright = 1\nfor i in range(n-1, -1, -1):\n    result[i] *= right\n    right *= arr[i]\nprint(*result)',
        ),

        AlgorithmicTask(
            id="three_sum",
            title="Three Sum",
            title_ru="Три числа с суммой ноль",
            difficulty=Difficulty.MEDIUM,
            category=Category.TWO_POINTERS,
            description_ru="Найдите все уникальные тройки чисел, дающие в сумме 0.",
            input_format="Массив через пробел.",
            output_format="Тройки чисел, каждая на новой строке (отсортированные).",
            examples=[{"input": "-1 0 1 2 -1 -4", "output": "-1 -1 2\n-1 0 1"}],
            test_cases=[
                TestCase("-1 0 1 2 -1 -4", "-1 -1 2\n-1 0 1"),
                TestCase("0 0 0", "0 0 0"),
                TestCase("1 2 3", "", is_hidden=True),
            ],
            hints=["Отсортируйте массив", "Фиксируйте первый элемент, для остальных — два указателя"],
            solution_code='arr = sorted(map(int, input().split()))\nn = len(arr)\nresults = []\nfor i in range(n - 2):\n    if i > 0 and arr[i] == arr[i-1]:\n        continue\n    left, right = i + 1, n - 1\n    while left < right:\n        s = arr[i] + arr[left] + arr[right]\n        if s == 0:\n            results.append((arr[i], arr[left], arr[right]))\n            while left < right and arr[left] == arr[left+1]:\n                left += 1\n            while left < right and arr[right] == arr[right-1]:\n                right -= 1\n            left += 1\n            right -= 1\n        elif s < 0:\n            left += 1\n        else:\n            right -= 1\nfor r in results:\n    print(*r)',
        ),

        AlgorithmicTask(
            id="spiral_matrix",
            title="Spiral Matrix",
            title_ru="Спиральный обход матрицы",
            difficulty=Difficulty.MEDIUM,
            category=Category.ARRAYS,
            description_ru="Выведите элементы матрицы в спиральном порядке.",
            input_format="Первая строка: n m. Далее n строк матрицы.",
            output_format="Элементы в спиральном порядке через пробел.",
            examples=[{"input": "3 3\n1 2 3\n4 5 6\n7 8 9", "output": "1 2 3 6 9 8 7 4 5"}],
            test_cases=[
                TestCase("3 3\n1 2 3\n4 5 6\n7 8 9", "1 2 3 6 9 8 7 4 5"),
                TestCase("1 4\n1 2 3 4", "1 2 3 4"),
                TestCase("2 2\n1 2\n3 4", "1 2 4 3", is_hidden=True),
            ],
            hints=["Используйте 4 границы: top, bottom, left, right", "Сужайте границы после каждого прохода"],
            solution_code='n, m = map(int, input().split())\nmatrix = [list(map(int, input().split())) for _ in range(n)]\nresult = []\ntop, bottom, left, right = 0, n-1, 0, m-1\nwhile top <= bottom and left <= right:\n    for j in range(left, right+1):\n        result.append(matrix[top][j])\n    top += 1\n    for i in range(top, bottom+1):\n        result.append(matrix[i][right])\n    right -= 1\n    if top <= bottom:\n        for j in range(right, left-1, -1):\n            result.append(matrix[bottom][j])\n        bottom -= 1\n    if left <= right:\n        for i in range(bottom, top-1, -1):\n            result.append(matrix[i][left])\n        left += 1\nprint(*result)',
        ),

        AlgorithmicTask(
            id="longest_palindrome",
            title="Longest Palindromic Substring",
            title_ru="Наидлиннейший палиндром-подстрока",
            difficulty=Difficulty.MEDIUM,
            category=Category.STRINGS,
            description_ru="Найдите самую длинную подстроку-палиндром.",
            input_format="Строка.",
            output_format="Длина наибольшего палиндрома.",
            examples=[{"input": "babad", "output": "3"}, {"input": "cbbd", "output": "2"}],
            test_cases=[
                TestCase("babad", "3"),
                TestCase("cbbd", "2"),
                TestCase("a", "1"),
                TestCase("aaaa", "4", is_hidden=True),
            ],
            hints=["Расширяйтесь из центра", "Проверяйте и нечётные, и чётные палиндромы"],
            solution_code='s = input()\ndef expand(l, r):\n    while l >= 0 and r < len(s) and s[l] == s[r]:\n        l -= 1\n        r += 1\n    return r - l - 1\nmax_len = 0\nfor i in range(len(s)):\n    len1 = expand(i, i)\n    len2 = expand(i, i + 1)\n    max_len = max(max_len, len1, len2)\nprint(max_len)',
        ),

        AlgorithmicTask(
            id="subarray_sum_k",
            title="Subarray Sum Equals K",
            title_ru="Подмассив с суммой K",
            difficulty=Difficulty.MEDIUM,
            category=Category.HASH_TABLE,
            description_ru="Найдите количество подмассивов с суммой равной k.",
            input_format="Первая строка: массив. Вторая строка: k.",
            output_format="Количество подмассивов.",
            examples=[{"input": "1 1 1\n2", "output": "2"}, {"input": "1 2 3\n3", "output": "2"}],
            test_cases=[
                TestCase("1 1 1\n2", "2"),
                TestCase("1 2 3\n3", "2"),
                TestCase("1 -1 0\n0", "3", is_hidden=True),
            ],
            hints=["Используйте префиксные суммы", "Храните счётчик префиксных сумм в словаре"],
            solution_code='from collections import defaultdict\narr = list(map(int, input().split()))\nk = int(input())\ncount = 0\nprefix_sum = 0\nprefix_counts = defaultdict(int)\nprefix_counts[0] = 1\nfor num in arr:\n    prefix_sum += num\n    count += prefix_counts[prefix_sum - k]\n    prefix_counts[prefix_sum] += 1\nprint(count)',
        ),
    ]


def get_additional_hard_tasks() -> List[AlgorithmicTask]:
    """Дополнительные сложные задачи."""
    return [
        AlgorithmicTask(
            id="max_histogram",
            title="Largest Rectangle in Histogram",
            title_ru="Максимальный прямоугольник в гистограмме",
            difficulty=Difficulty.HARD,
            category=Category.STACK_QUEUE,
            description_ru="Найдите площадь наибольшего прямоугольника в гистограмме.",
            input_format="Высоты столбцов через пробел.",
            output_format="Максимальная площадь.",
            examples=[{"input": "2 1 5 6 2 3", "output": "10"}],
            test_cases=[
                TestCase("2 1 5 6 2 3", "10"),
                TestCase("2 4", "4"),
                TestCase("1 1 1 1", "4", is_hidden=True),
            ],
            hints=["Используйте стек", "Храните индексы столбцов"],
            solution_code='heights = list(map(int, input().split()))\nstack = []\nmax_area = 0\nfor i, h in enumerate(heights + [0]):\n    while stack and heights[stack[-1]] > h:\n        height = heights[stack.pop()]\n        width = i if not stack else i - stack[-1] - 1\n        max_area = max(max_area, height * width)\n    stack.append(i)\nprint(max_area)',
        ),

        AlgorithmicTask(
            id="trapping_water",
            title="Trapping Rain Water",
            title_ru="Ловушка для воды",
            difficulty=Difficulty.HARD,
            category=Category.TWO_POINTERS,
            description_ru="Сколько воды можно накопить между столбцами после дождя?",
            input_format="Высоты столбцов через пробел.",
            output_format="Объём воды.",
            examples=[{"input": "0 1 0 2 1 0 1 3 2 1 2 1", "output": "6"}],
            test_cases=[
                TestCase("0 1 0 2 1 0 1 3 2 1 2 1", "6"),
                TestCase("4 2 0 3 2 5", "9"),
                TestCase("1 2 3", "0", is_hidden=True),
            ],
            hints=["Вода над позицией = min(max_left, max_right) - height", "Два указателя или предвычисление"],
            solution_code='height = list(map(int, input().split()))\nn = len(height)\nif n < 3:\n    print(0)\nelse:\n    left_max = [0] * n\n    right_max = [0] * n\n    left_max[0] = height[0]\n    for i in range(1, n):\n        left_max[i] = max(left_max[i-1], height[i])\n    right_max[n-1] = height[n-1]\n    for i in range(n-2, -1, -1):\n        right_max[i] = max(right_max[i+1], height[i])\n    water = sum(min(left_max[i], right_max[i]) - height[i] for i in range(n))\n    print(water)',
        ),

        AlgorithmicTask(
            id="regex_match",
            title="Regular Expression Matching",
            title_ru="Регулярные выражения",
            difficulty=Difficulty.HARD,
            category=Category.DYNAMIC,
            description_ru="Реализуйте простое сопоставление с '.' (любой символ) и '*' (ноль или более предыдущего).",
            input_format="Строка s.\nПаттерн p.",
            output_format="YES или NO.",
            examples=[{"input": "aa\na", "output": "NO"}, {"input": "aa\na*", "output": "YES"}],
            test_cases=[
                TestCase("aa\na", "NO"),
                TestCase("aa\na*", "YES"),
                TestCase("ab\n.*", "YES"),
                TestCase("aab\nc*a*b", "YES", is_hidden=True),
            ],
            hints=["Используйте ДП", "dp[i][j] — совпадают ли s[:i] и p[:j]"],
            solution_code='s = input()\np = input()\nm, n = len(s), len(p)\ndp = [[False] * (n + 1) for _ in range(m + 1)]\ndp[0][0] = True\nfor j in range(1, n + 1):\n    if p[j-1] == "*":\n        dp[0][j] = dp[0][j-2]\nfor i in range(1, m + 1):\n    for j in range(1, n + 1):\n        if p[j-1] == "*":\n            dp[i][j] = dp[i][j-2]\n            if p[j-2] == "." or p[j-2] == s[i-1]:\n                dp[i][j] = dp[i][j] or dp[i-1][j]\n        elif p[j-1] == "." or p[j-1] == s[i-1]:\n            dp[i][j] = dp[i-1][j-1]\nprint("YES" if dp[m][n] else "NO")',
        ),

        AlgorithmicTask(
            id="min_window",
            title="Minimum Window Substring",
            title_ru="Минимальное окно с подстрокой",
            difficulty=Difficulty.HARD,
            category=Category.TWO_POINTERS,
            description_ru="Найдите минимальную подстроку s, содержащую все символы t.",
            input_format="Строка s.\nСтрока t.",
            output_format="Минимальная подстрока или пустая строка.",
            examples=[{"input": "ADOBECODEBANC\nABC", "output": "BANC"}],
            test_cases=[
                TestCase("ADOBECODEBANC\nABC", "BANC"),
                TestCase("a\na", "a"),
                TestCase("a\naa", "", is_hidden=True),
            ],
            hints=["Скользящее окно", "Храните счётчик нужных символов"],
            solution_code='from collections import Counter\ns = input()\nt = input()\nif not t or not s:\n    print("")\nelse:\n    need = Counter(t)\n    have = 0\n    required = len(need)\n    left = 0\n    min_len = float("inf")\n    result = ""\n    window = {}\n    for right in range(len(s)):\n        c = s[right]\n        window[c] = window.get(c, 0) + 1\n        if c in need and window[c] == need[c]:\n            have += 1\n        while have == required:\n            if right - left + 1 < min_len:\n                min_len = right - left + 1\n                result = s[left:right+1]\n            lc = s[left]\n            window[lc] -= 1\n            if lc in need and window[lc] < need[lc]:\n                have -= 1\n            left += 1\n    print(result)',
        ),

        AlgorithmicTask(
            id="word_ladder",
            title="Word Ladder",
            title_ru="Цепочка слов",
            difficulty=Difficulty.HARD,
            category=Category.GRAPHS,
            description_ru="Найдите длину кратчайшей цепочки слов от beginWord до endWord, меняя по одной букве.",
            input_format="Начальное слово.\nКонечное слово.\nСлова словаря через пробел.",
            output_format="Длина цепочки или 0.",
            examples=[{"input": "hit\ncog\nhot dot dog lot log cog", "output": "5"}],
            test_cases=[
                TestCase("hit\ncog\nhot dot dog lot log cog", "5"),
                TestCase("hit\ncog\nhot dot dog lot log", "0"),
                TestCase("a\nc\na b c", "2", is_hidden=True),
            ],
            hints=["BFS", "Генерируйте все возможные следующие слова"],
            solution_code='from collections import deque\nbegin = input()\nend = input()\nwords = set(input().split())\nif end not in words:\n    print(0)\nelse:\n    queue = deque([(begin, 1)])\n    visited = {begin}\n    found = False\n    while queue and not found:\n        word, length = queue.popleft()\n        for i in range(len(word)):\n            for c in "abcdefghijklmnopqrstuvwxyz":\n                next_word = word[:i] + c + word[i+1:]\n                if next_word == end:\n                    print(length + 1)\n                    found = True\n                    break\n                if next_word in words and next_word not in visited:\n                    visited.add(next_word)\n                    queue.append((next_word, length + 1))\n            if found:\n                break\n    if not found:\n        print(0)',
        ),
    ]


def get_all_additional_tasks() -> List[AlgorithmicTask]:
    """Все дополнительные задачи."""
    return (
        get_additional_easy_tasks() +
        get_additional_medium_tasks() +
        get_additional_hard_tasks()
    )
