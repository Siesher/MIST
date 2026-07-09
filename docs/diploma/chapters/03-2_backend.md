Серверная часть системы MITS реализована на фреймворке FastAPI — асинхронном Python-фреймворке, предоставляющем автоматическую генерацию OpenAPI-документации, нативную поддержку WebSocket и встроенную валидацию данных через Pydantic. Выбор FastAPI обусловлен низкими накладными расходами при асинхронных операциях ввода-вывода, что критично для потоковой передачи токенов LLM через WebSocket.

## Структура API

Маршрутизация реализована через объект `APIRouter`, регистрируемый в `app/api/v1/router.py`. Все эндпоинты имеют префикс `/api/v1`. Итоговое API включает 25+ эндпоинтов, сгруппированных по модулям:

| Модуль | Эндпоинты | Назначение |
|---|---|---|
| `auth.py` | POST `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout` | Аутентификация |
| `sessions.py` | GET/POST `/sessions`, GET/PATCH/DELETE `/sessions/{id}` | Управление сессиями |
| `chat.py` | POST `/chat/message` | HTTP-чат (без стриминга) |
| `websocket.py` | WS `/ws/{sessionId}` | WebSocket-стриминг |
| `analytics.py` | GET `/analytics/progress`, `/analytics/domains`, `/analytics/sessions` | Аналитика |
| `tasks.py` | GET `/tasks`, POST `/tasks/generate` | Банк задач |
| `knowledge.py` | GET `/knowledge/graph`, POST `/knowledge/ingest` | Граф знаний |
| `students.py` | GET/PATCH `/students/me`, GET `/students/me/mastery` | Профиль ученика |
| `metrics.py` | GET `/metrics/system`, `/metrics/agents` | Системные метрики |

## Аутентификация: JWT + Argon2

Схема аутентификации использует пару токенов: access-токен с коротким сроком жизни (30 минут) и refresh-токен с длительным (30 дней). Такая схема минимизирует ущерб при компрометации access-токена: злоумышленник имеет ограниченное время для использования перехваченного токена.

Пароли хешируются алгоритмом Argon2id через библиотеку `argon2-cffi` — победителем конкурса Password Hashing Competition 2015. Argon2id устойчив как к атакам на специализированном железе (ASIC), так и к атакам по побочным каналам (time-side-channel attacks). Параметры: память 65536 КиБ, 3 итерации, 4 параллельных потока.

JWT-токены генерируются библиотекой PyJWT с алгоритмом HS256. Полезная нагрузка access-токена содержит `sub` (user_id), `type: "access"` и `exp` (время истечения). Refresh-токены хранятся в БД в виде хеша (SHA-256 от токена), что позволяет инвалидировать их при необходимости:

```python
def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

Защищённые эндпоинты используют FastAPI Dependency `get_current_user`, который извлекает токен из заголовка `Authorization: Bearer <token>`, верифицирует его и загружает пользователя из БД. WebSocket-эндпоинт принимает токен через query-параметр `?token=<jwt>`, так как стандарт WebSocket не поддерживает произвольные заголовки при первоначальном рукопожатии.

## ORM: SQLAlchemy 2.0

Для работы с базой данных используется SQLAlchemy 2.0 с новым стилем объявления моделей через аннотации типов (`Mapped[T]`). База данных — SQLite, хранящаяся в файле `data/mits.db`. Выбор SQLite обусловлен нулевой конфигурацией и портативностью: вся БД помещается в один файл, что упрощает развёртывание и резервное копирование.

Схема данных включает шесть таблиц:

```python
class UserTable(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    preferred_mode: Mapped[str] = mapped_column(String(30), default="guided_learning")
    sessions: Mapped[list["SessionTable"]] = relationship(cascade="all, delete-orphan")


class SessionTable(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(30), default="guided_learning")
    topic: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active")
    is_solved: Mapped[bool] = mapped_column(Boolean, default=False)


class MessageTable(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))      # user | assistant
    content: Mapped[str] = mapped_column(Text)
    move_type: Mapped[str | None] = mapped_column(String(30))  # scaffolding | hint | ...
    thinking: Mapped[str | None] = mapped_column(Text)         # thinking-блок

class RefreshTokenTable(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
```

Дополнительно присутствуют таблицы `ExperimentTable` и `SourceTable` для A/B-тестирования режимов обучения и хранения загружаемых источников знаний соответственно. Для асинхронных операций используется `AsyncSession` с фабрикой `async_session_factory`, подключаемой через FastAPI Dependency.

## WebSocket Handler

WebSocket-эндпоинт (`/ws/{session_id}`) реализован как отдельный маршрут вне стандартного API-роутера. Обработчик следует следующему протоколу взаимодействия:

1. При установке соединения — верификация JWT-токена из query-параметра, проверка существования сессии, отправка события `connection_ready` с текущим состоянием сессии.
2. В цикле ожидания — получение JSON-сообщений, диспетчеризация по типу (`message`, `ping`, `set_mode`).
3. При получении `message` — запуск потоковой генерации через `OrchestratorService` в отдельном потоке (через `ThreadPoolExecutor`), помещение токенов в `asyncio.Queue`, асинхронная отправка их клиенту.
4. По завершении генерации — отправка события `message_complete` с полными метаданными (move_type, knowledge_state, pipeline_trace).

Мост между синхронным генератором LLM и асинхронным WebSocket-циклом реализован через `asyncio.Queue` и функцию `asyncio.get_event_loop().run_in_executor()`, подробнее описанную в разделе 2.6. При разрыве соединения (`WebSocketDisconnect`) обработчик корректно завершает генерацию и освобождает ресурсы.

Формат WebSocket-сообщений описывается следующими типами событий:

| Тип события (сервер → клиент) | Содержимое |
|---|---|
| `connection_ready` | `session_id`, `session_state` |
| `thinking_token` | `content: str` (фрагмент reasoning) |
| `token` | `content: str` (фрагмент ответа) |
| `message_complete` | `move_type`, `knowledge_state`, `metrics` |
| `error` | `code`, `message`, `recoverable: bool` |
