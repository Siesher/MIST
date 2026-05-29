# Design: Атрибуция/цитаты источников в ответах тьютора

**Дата:** 2026-05-29
**Статус:** approved (чипы+фрагмент, персист в БД)
**Ветка:** 019-ns-vstar-dpo

## Проблема

Агент использует загруженные источники (`search_in_source`/`read_source`), но в
ответе не указывает, из какого источника взят факт. Нет доверия/проверяемости.
Нужно: показывать «Источники» под ответом — чип с названием (ссылка на /sources)
+ короткий распознанный фрагмент. Цитаты переживают перезагрузку (персист в БД).

## Принцип захвата

Не угадывать по тексту, а **перехватывать фактически прочитанное**: в
`_tool_executor` (orchestrator_service.py:1321) при вызове source-инструмента
парсить JSON-результат и собирать `{source_id, title, excerpt}` (дедуп по
source_id). Это реальная атрибуция (что агент прочитал), а не пост-фактум.

## Компоненты

### Backend
1. **Захват:** обёртка `_tool_executor` копит `citations` из результатов
   `search_in_source` (hits[].source_id/title/excerpt), `read_source`
   (source_id/title + первые ~200 симв.), игнорируя `list_sources`.
2. **Эмиссия:** `citations` добавляется в событие `response_complete`
   (orchestrator_service.py:~1510, в объект `response`) и в `tutor_msg`.
3. **Схема (REST-паритет):** `TutorResponseData.citations: Optional[List[Citation]]`
   (chat.py:128). `Citation = {source_id, title, excerpt}`.
4. **Персист:** новая nullable-колонка `MessageTable.citations_json: Text`
   (tables.py). Лёгкая идемпотентная миграция в `init_db` (PRAGMA table_info →
   ALTER ADD COLUMN, т.к. в репо нет alembic). `StoredMessage.citations` поле;
   `_save_message` пишет JSON; `_row_to_session` читает; история-эндпоинт отдаёт.

### Frontend
5. **Тип:** `Message.citations?: Array<{source_id,title,excerpt}>` (types/api.ts);
   `WSResponseComplete.response.citations`.
6. **useChat:** извлечь `msg.response.citations` в `tutorMessage`.
7. **История:** при загрузке сессии маппить citations из ответа сервера.
8. **Рендер:** блок «Источники» в Message.tsx после контента — чипы (Link на
   /sources) + усечённый фрагмент. Проброс пропа от места рендера.

## Поток

```
агент → search_in_source → _tool_executor (capture {src,title,excerpt})
   → response_complete{response:{content, citations:[…]}} (+ persist citations_json)
   → WS → useChat → Message.citations → блок «Источники» (чип→/sources + фрагмент)
```

## Обработка ошибок
- Нет source-вызовов → citations пуст → блок не рендерится.
- Битый JSON результата инструмента → пропустить (try/except в capture).
- Старая БД без колонки → идемпотентный ALTER при старте.
- Парс citations_json при чтении в try/except (как task_json).

## Тесты
- Backend: юнит на функцию-парсер результата инструмента → citations (search/read,
  дедуп, list игнор, битый JSON).
- Frontend: tsc.

## Вне scope
- Кликабельная подсветка конкретного источника на /sources (ссылка ведёт на
  список). Инлайн-сноски в тексте ответа (только блок под ответом).
