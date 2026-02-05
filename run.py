"""
MITS — Скрипт запуска системы

Использование:
    python run.py              - Единый интерфейс (рекомендуется)
    python run.py math         - Только математика
    python run.py coding       - Только программирование
    python run.py test         - Запуск тестов
"""

import sys
import os

# Фикс кодировки для Windows консоли
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "unified"
    
    print("=" * 60)
    print("🐝 MITS — Интеллектуальная система обучения")
    print("=" * 60)
    
    if mode == "test":
        print("🧪 Запуск тестов...")
        from tests.test_coding import main as run_tests
        success = run_tests()
        sys.exit(0 if success else 1)
    
    elif mode == "coding":
        print("💻 Режим: Программирование")
        from interface.coding_app import create_interface
        interface = create_interface()
    
    elif mode == "math":
        print("📐 Режим: Математика")
        from interface.app_v2 import create_app
        interface = create_app()
    
    else:  # unified
        print("🎯 Режим: Единый интерфейс")
        from interface.unified_app import create_interface
        interface = create_interface()
    
    print()
    print("🌐 Откройте: http://localhost:7860")
    print("=" * 60)
    
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )


if __name__ == "__main__":
    main()
