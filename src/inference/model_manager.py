#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер моделей MITS.

Поддерживает переключение между различными бэкендами:
- Ollama (локальный инференс)
- HuggingFace (с квантованием)
- Cerebras API (для генерации данных)
"""

from enum import Enum
from typing import Optional, Dict, Any, Union, Protocol
from dataclasses import dataclass, field
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelBackend(Enum):
    """Доступные бэкенды для запуска моделей."""
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"
    CEREBRAS = "cerebras"


class ModelPurpose(Enum):
    """Назначение модели в системе."""
    TUTOR = "tutor"           # Основной репетитор
    DRAFT = "draft"           # Черновая модель для спекулятивного декодирования
    TEACHER = "teacher"       # Модель-учитель для генерации данных
    EMBEDDING = "embedding"   # Модель эмбеддингов для RAG
    PROFILER = "profiler"     # Модель для диагностики ошибок


@dataclass
class ModelConfig:
    """Конфигурация модели."""
    name: str
    backend: ModelBackend
    purpose: ModelPurpose

    # Параметры для Ollama
    ollama_model: Optional[str] = None

    # Параметры для HuggingFace
    hf_model_path: Optional[str] = None
    hf_adapter_path: Optional[str] = None
    quantize: bool = True
    quantize_bits: int = 4

    # Параметры для Cerebras
    cerebras_model: Optional[str] = None

    # Общие параметры
    max_tokens: int = 2048
    temperature: float = 0.7
    context_length: int = 4096

    # Оценка ресурсов
    estimated_vram_gb: float = 0.0
    estimated_ram_gb: float = 0.0


class LLMClientProtocol(Protocol):
    """Протокол для клиентов LLM."""

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        ...

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ):
        ...


# Предустановленные конфигурации моделей
MODEL_PRESETS: Dict[str, ModelConfig] = {
    # ============================================================
    # ОСНОВНЫЕ МОДЕЛИ ДЛЯ РЕПЕТИТОРА (RTX 2080 8GB VRAM)
    # ============================================================

    # РЕКОМЕНДУЕМАЯ: GLM-STEM-42exp (REAP-pruned, 42 experts)
    # - 33% меньше параметров, сохраняет STEM качество
    # - GSM8K ~95%, оптимизирован для математики и программирования
    # - Калибровка на STEM датасете (1490 примеров)
    "glm-stem-42exp-tutor": ModelConfig(
        name="GLM-STEM-42exp (REAP-pruned) [RECOMMENDED]",
        backend=ModelBackend.OLLAMA,
        purpose=ModelPurpose.TUTOR,
        ollama_model="glm-stem-42exp",
        hf_model_path="Siesher/glm-stem-42exp-gguf",
        estimated_vram_gb=5.5,  # 33% меньше чем original
        estimated_ram_gb=6.0,
        max_tokens=2048,
        temperature=0.2,  # GLM-optimized
        context_length=4096,
    ),

    # FALLBACK: GLM-4.7-Flash (original 64 experts)
    # - GSM8K ~95-98%, AIME ~90%
    # - Partial offload: 25 GPU layers + 22 CPU MoE layers
    # - Используется если pruned модель недоступна
    "glm-4.7-flash-tutor": ModelConfig(
        name="GLM-4.7-Flash (64 experts) [FALLBACK]",
        backend=ModelBackend.OLLAMA,
        purpose=ModelPurpose.TUTOR,
        ollama_model="glm-4.7-flash",
        hf_model_path="unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF",
        estimated_vram_gb=7.2,  # 25 layers Q4_K_M
        estimated_ram_gb=8.0,   # remaining layers + KV cache
        max_tokens=2048,
        temperature=0.2,  # GLM-optimized, higher causes repetition
        context_length=4096,
    ),

    # FALLBACK: DeepSeek-R1-Distill-8B
    # - GSM8K 80-85%, strong reasoning (distilled from R1 671B)
    # - Fits entirely on GPU
    # - Stable, well-tested
    "deepseek-r1-8b-tutor": ModelConfig(
        name="DeepSeek-R1-Distill-8B (Fallback)",
        backend=ModelBackend.OLLAMA,
        purpose=ModelPurpose.TUTOR,
        ollama_model="deepseek-r1:8b",
        estimated_vram_gb=6.5,
        estimated_ram_gb=2.0,
        max_tokens=2048,
        temperature=0.3,
        context_length=4096,
    ),

    # Альтернатива: Qwen3-8B-Instruct
    # - Лучший баланс STEM: MMLU 76.89, GPQA 63.3, Coding 67.65
    # - Отлично для математики, программирования, физики, химии
    # - Хорошо переносит квантование
    # - 32K контекст
    "qwen3-8b-tutor": ModelConfig(
        name="Qwen3-8B-Instruct (Tutor)",
        backend=ModelBackend.OLLAMA,
        purpose=ModelPurpose.TUTOR,
        ollama_model="qwen3:8b",
        hf_model_path="Qwen/Qwen3-8B-Instruct",
        estimated_vram_gb=5.0,  # 4-bit quantization
        max_tokens=2048,
        context_length=32768,
    ),

    # Альтернатива для math-only: Phi-4-mini-flash-reasoning
    # - 3.8B параметров, 92.45% Math-500
    # - Быстрее, но только математика
    "phi4-mini-reasoning": ModelConfig(
        name="Phi-4-mini-flash-reasoning (Math only)",
        backend=ModelBackend.OLLAMA,
        purpose=ModelPurpose.TUTOR,
        ollama_model="phi4-mini-reasoning:latest",
        hf_model_path="microsoft/Phi-4-mini-flash-reasoning",
        estimated_vram_gb=2.5,
        max_tokens=2048,
        context_length=65536,
    ),

    # Легкая альтернатива: Qwen3-4B
    "qwen3-4b-tutor": ModelConfig(
        name="Qwen3-4B (Lightweight)",
        backend=ModelBackend.OLLAMA,
        purpose=ModelPurpose.TUTOR,
        ollama_model="qwen3:4b",
        hf_model_path="Qwen/Qwen3-4B-Instruct",
        estimated_vram_gb=2.5,
        max_tokens=2048,
        context_length=32768,
    ),

    # ============================================================
    # МОДЕЛИ-УЧИТЕЛИ ДЛЯ ГЕНЕРАЦИИ ДАННЫХ
    # ============================================================

    # ЛУЧШАЯ: Nemotron-Cascade-8B-Thinking
    # - 90.5% AIME 2024, 83.2% AIME 2025 (сравнимо с DeepSeek-R1 671B!)
    # - Идеально для генерации обучающих диалогов
    "nemotron-cascade-8b-teacher": ModelConfig(
        name="Nemotron-Cascade-8B-Thinking (Teacher)",
        backend=ModelBackend.OLLAMA,
        purpose=ModelPurpose.TEACHER,
        ollama_model="nemotron-cascade:8b-thinking",
        hf_model_path="nvidia/Nemotron-Cascade-8B-Thinking",
        estimated_vram_gb=5.0,  # 4-bit quantization
        estimated_ram_gb=10.0,
        max_tokens=4096,
        temperature=0.6,
    ),

    # Cerebras API - бесплатно, очень мощная модель
    "cerebras-qwen-235b": ModelConfig(
        name="Qwen-3-235B via Cerebras",
        backend=ModelBackend.CEREBRAS,
        purpose=ModelPurpose.TEACHER,
        cerebras_model="qwen-3-235b-a22b-instruct-2507",
        estimated_vram_gb=0.0,  # API, не локально
        max_tokens=4096,
    ),

    # Fallback учитель
    "nemotron-30b-teacher": ModelConfig(
        name="Nemotron-3-Nano-30B (Teacher)",
        backend=ModelBackend.OLLAMA,
        purpose=ModelPurpose.TEACHER,
        ollama_model="nemotron-3-nano:30b",
        estimated_vram_gb=6.0,
        estimated_ram_gb=20.0,
        max_tokens=4096,
    ),

    # ============================================================
    # ЧЕРНОВЫЕ МОДЕЛИ (Speculative Decoding)
    # ============================================================

    "qwen-0.5b-draft": ModelConfig(
        name="Qwen2.5-0.5B (Draft)",
        backend=ModelBackend.OLLAMA,
        purpose=ModelPurpose.DRAFT,
        ollama_model="qwen2.5:0.5b",
        hf_model_path="Qwen/Qwen2.5-0.5B-Instruct",
        estimated_vram_gb=0.5,
        max_tokens=512,
    ),

    # ============================================================
    # МОДЕЛИ ЭМБЕДДИНГОВ (RAG)
    # ============================================================

    "minilm-embedding": ModelConfig(
        name="MiniLM-L12 (Embedding)",
        backend=ModelBackend.HUGGINGFACE,
        purpose=ModelPurpose.EMBEDDING,
        hf_model_path="paraphrase-multilingual-MiniLM-L12-v2",
        estimated_vram_gb=0.1,
        quantize=False,
    ),
}


class ModelManager:
    """
    Централизованное управление моделями MITS.

    Особенности:
    - Ленивая загрузка моделей (загружаются при первом использовании)
    - Автоматический выбор бэкенда
    - Мониторинг использования VRAM
    - Кэширование загруженных моделей
    - Поддержка переключения между моделями

    Паттерн: Singleton
    """

    _instance = None
    _models: Dict[str, Any] = {}
    _configs: Dict[str, ModelConfig] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._models = {}
        self._configs = {}
        self._default_backend = ModelBackend.OLLAMA
        self._initialized = True

        logger.info("ModelManager инициализирован")

    def set_default_backend(self, backend: ModelBackend):
        """Установка бэкенда по умолчанию."""
        self._default_backend = backend
        logger.info(f"Бэкенд по умолчанию: {backend.value}")

    def register_config(self, key: str, config: ModelConfig):
        """Регистрация конфигурации модели."""
        self._configs[key] = config
        logger.debug(f"Зарегистрирована конфигурация: {key}")

    def get_model(
        self,
        purpose: ModelPurpose = ModelPurpose.TUTOR,
        preset: Optional[str] = None,
        backend: Optional[ModelBackend] = None,
        force_reload: bool = False
    ) -> LLMClientProtocol:
        """
        Получение модели для указанной цели.

        Args:
            purpose: Назначение модели (tutor, draft, teacher, etc.)
            preset: Имя пресета из MODEL_PRESETS
            backend: Явный выбор бэкенда (переопределяет пресет)
            force_reload: Принудительная перезагрузка модели

        Returns:
            Клиент модели, совместимый с LLMClientProtocol
        """
        # Определяем конфигурацию
        if preset and preset in MODEL_PRESETS:
            config = MODEL_PRESETS[preset]
        elif preset and preset in self._configs:
            config = self._configs[preset]
        else:
            # Выбираем подходящий пресет по назначению
            config = self._get_default_config(purpose)

        if backend:
            config.backend = backend

        cache_key = f"{config.name}_{config.backend.value}"

        # Проверяем кэш
        if cache_key in self._models and not force_reload:
            logger.debug(f"Модель из кэша: {cache_key}")
            return self._models[cache_key]

        # Загружаем модель
        client = self._load_model(config)
        self._models[cache_key] = client

        logger.info(
            f"Модель загружена: {config.name} "
            f"(backend={config.backend.value}, VRAM~{config.estimated_vram_gb}GB)"
        )

        return client

    def _get_default_config(self, purpose: ModelPurpose) -> ModelConfig:
        """Получение конфигурации по умолчанию для назначения."""
        defaults = {
            ModelPurpose.TUTOR: "glm-stem-42exp-tutor",  # REAP-pruned, STEM-оптимизирован
            ModelPurpose.DRAFT: "qwen-0.5b-draft",
            ModelPurpose.TEACHER: "nemotron-cascade-8b-teacher",  # 90.5% AIME
            ModelPurpose.EMBEDDING: "minilm-embedding",
            ModelPurpose.PROFILER: "qwen3-4b-tutor",  # Легче для диагностики
        }

        preset_name = defaults.get(purpose, "qwen3-8b-tutor")
        return MODEL_PRESETS[preset_name]

    def _load_model(self, config: ModelConfig) -> LLMClientProtocol:
        """Загрузка модели в зависимости от бэкенда."""

        if config.backend == ModelBackend.OLLAMA:
            return self._load_ollama_model(config)
        elif config.backend == ModelBackend.HUGGINGFACE:
            return self._load_hf_model(config)
        elif config.backend == ModelBackend.CEREBRAS:
            return self._load_cerebras_model(config)
        else:
            raise ValueError(f"Неизвестный бэкенд: {config.backend}")

    def _load_ollama_model(self, config: ModelConfig) -> LLMClientProtocol:
        """Загрузка модели через Ollama."""
        try:
            from src.models.llm_client import LLMClient

            return LLMClient(
                model=config.ollama_model,
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
        except ImportError:
            logger.error("LLMClient не найден. Проверьте src/models/llm_client.py")
            raise

    def _load_hf_model(self, config: ModelConfig) -> LLMClientProtocol:
        """Загрузка модели через HuggingFace."""
        try:
            from src.models.hf_client import HuggingFaceClient

            return HuggingFaceClient(
                model_path=config.hf_model_path,
                adapter_path=config.hf_adapter_path,
                quantize=config.quantize,
                quantize_bits=config.quantize_bits,
                max_tokens=config.max_tokens
            )
        except ImportError:
            logger.warning(
                "HuggingFaceClient не найден. "
                "Fallback на Ollama."
            )
            return self._load_ollama_model(config)

    def _load_cerebras_model(self, config: ModelConfig) -> LLMClientProtocol:
        """Загрузка модели через Cerebras API."""
        try:
            from src.models.cerebras_client import CerebrasClient

            return CerebrasClient(
                model=config.cerebras_model,
                max_tokens=config.max_tokens
            )
        except ImportError:
            logger.warning(
                "CerebrasClient не найден. "
                "Используйте training/scripts/cerebras_dialog_generator.py"
            )
            raise

    def unload_model(self, cache_key: str):
        """Выгрузка модели из памяти."""
        if cache_key in self._models:
            del self._models[cache_key]
            logger.info(f"Модель выгружена: {cache_key}")

            # Принудительная очистка GPU памяти
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

    def unload_all(self):
        """Выгрузка всех моделей."""
        keys = list(self._models.keys())
        for key in keys:
            self.unload_model(key)
        logger.info("Все модели выгружены")

    def get_loaded_models(self) -> Dict[str, str]:
        """Получение списка загруженных моделей."""
        return {
            key: str(type(model).__name__)
            for key, model in self._models.items()
        }

    def estimate_total_vram(self) -> float:
        """Оценка общего потребления VRAM."""
        total = 0.0
        for key in self._models:
            # Извлекаем имя конфига из ключа
            for preset_name, config in MODEL_PRESETS.items():
                if config.name in key:
                    total += config.estimated_vram_gb
                    break
        return total

    def get_available_presets(
        self,
        purpose: Optional[ModelPurpose] = None,
        max_vram_gb: Optional[float] = None
    ) -> Dict[str, ModelConfig]:
        """
        Получение доступных пресетов с фильтрацией.

        Args:
            purpose: Фильтр по назначению
            max_vram_gb: Максимальное потребление VRAM

        Returns:
            Словарь доступных пресетов
        """
        result = {}

        for name, config in MODEL_PRESETS.items():
            if purpose and config.purpose != purpose:
                continue
            if max_vram_gb and config.estimated_vram_gb > max_vram_gb:
                continue
            result[name] = config

        return result


# Фабричная функция для удобства
def get_model_manager() -> ModelManager:
    """Получение синглтона ModelManager."""
    return ModelManager()


def create_client(
    purpose: ModelPurpose = ModelPurpose.TUTOR,
    backend: Optional[ModelBackend] = None
) -> LLMClientProtocol:
    """
    Фабричная функция для создания клиента модели.

    Args:
        purpose: Назначение модели
        backend: Бэкенд (опционально)

    Returns:
        Клиент модели

    Example:
        >>> client = create_client(ModelPurpose.TUTOR)
        >>> response = client.generate("Помоги решить уравнение")
    """
    manager = get_model_manager()
    return manager.get_model(purpose=purpose, backend=backend)


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Model Manager Demo ===\n")

    manager = get_model_manager()

    # Показываем доступные пресеты для 8GB VRAM
    print("Доступные модели для 8GB VRAM:")
    presets = manager.get_available_presets(max_vram_gb=8.0)
    for name, config in presets.items():
        print(f"  {name}: {config.name} ({config.estimated_vram_gb}GB VRAM)")

    print("\nМодели для репетитора:")
    tutor_presets = manager.get_available_presets(
        purpose=ModelPurpose.TUTOR,
        max_vram_gb=8.0
    )
    for name, config in tutor_presets.items():
        print(f"  {name}: {config.name}")

    # Пример загрузки (требует настроенный Ollama)
    # client = manager.get_model(purpose=ModelPurpose.TUTOR)
    # response = client.generate("Привет!")
    # print(response)
