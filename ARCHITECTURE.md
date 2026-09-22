# ai-call-analyzer: Детальний план розробки

## Статус на 22.09.2026

Галочки в фазах нижче — первісний план; фактичний стан перевірено так:

| Що | Стан | Чим перевірено |
| :--- | :--- | :--- |
| `poetry install` | ✅ | `poetry install` (Poetry 2.3.4, Python 3.12) |
| LocalStack піднімається, бакет і таблиця створюються автоматично | ✅ | `docker compose ... up -d`, `docker exec localstack-main awslocal s3 ls` / `dynamodb list-tables` |
| Lint | ✅ | `poetry run ruff check .` — 0 помилок |
| Unit-тести | ✅ | `poetry run pytest tests/unit/` — 34 passed |
| Інтеграційний тест (LocalStack, Azure і Groq замокані) | ✅ | `poetry run pytest tests/integration/` — 1 passed |
| MP3 приймається Azure SDK | ✅ | декодування miniaudio → push-стрім; recognizer створюється |
| Невірний ключ Azure → зрозуміла помилка без повторів | ✅ | запуск демо з фейковим ключем: `AuthenticationFailure (401)`, код виходу 1 |
| Повний прогін з реальними Azure + Groq | ⏳ | потребує справжніх ключів у `.env` |

## 0. Контекст та обмеження

### Бізнес-проблема
Sales-менеджери не мають об'єктивної оцінки якості дзвінків своїх продавців. Вони змушені або слухати дзвінки вручну (витрачати години), або оцінювати тільки за кінцевим результатом (виручкою). Потрібна система, яка автоматично аналізує аудіо дзвінка і дає об'єктивну оцінку 0-100.

### Вхідні дані
- Аудіофайл у форматі MP3 або WAV (тривалість 1-10 хвилин)
- Тестовий дзвінок (можна записати самостійно або взяти готовий)

### Вихід
- Транскрипція аудіо в текст (Azure Speech Services)
- Оцінка якості дзвінка 0-100 (Groq API, модель `openai/gpt-oss-120b`)
- Структурований JSON-результат: `{ "transcript": "...", "score": 85, "reasoning": "..." }`
- Lambda-подібна структура проекту (готовність до деплою в AWS)
- Локальне AWS-оточення (LocalStack: S3, DynamoDB)
- Повна документація в README

### Обмеження (прийняті як даність)
- Локальний запуск через Python-скрипти (без реального AWS)
- LocalStack для емуляції AWS-сервісів (безкоштовно, локально; образ закріплено на `4.14.0`, бо новіші з 23.03.2026 вимагають auth token)
- Один користувач, без авторизації
- Без реального деплою в AWS (тільки локальна демонстрація)
- Використання безкоштовних API-ключів (Azure Speech Free Tier, Groq Free Tier)

### Архітектурні рішення

| Рішення | Альтернатива | Чому обрали |
| :--- | :--- | :--- |
| **Azure Speech Services** | AWS Transcribe | Безкоштовний tier (5 годин/міс), краща діаризація |
| **Groq API (`openai/gpt-oss-120b`)** | Azure OpenAI | Безкоштовний tier, не потребує реєстрації в Azure OpenAI. Llama 3.3 70B, з якої починали, Groq вимкнув 16.08.2026; модель задається через `GROQ_MODEL` |
| **LocalStack 4.14.0** | Реальний AWS | Безкоштовно, працює локально, не потребує кредитної картки |
| **miniaudio: MP3/WAV → 16 кГц моно PCM** | GStreamer + стиснений потік Azure | Ставиться через pip без системних бібліотек; `AudioConfig(filename=...)` в Azure SDK приймає лише WAV |
| **`meeting_id` = SHA-256 вмісту аудіо** | `uuid4()` на кожен запуск | Той самий запис → той самий ID → транскрипт і оцінка з кешу, без повторної оплати API |
| **Lambda-подібна структура** | Монолітний скрипт | Демонструє розуміння serverless-архітектури |
| **Structured JSON-логи** | `print()` | Готовність до CloudWatch, легше дебажити |
| **Exponential backoff** | Фіксований retry | Production-патерн, запобігає rate limiting |
| **Poetry** | `requirements.txt` | Фіксація залежностей, відтворюваність |

---

## 1. Структура файлів та відповідальність

```
/ai-call-analyzer
├── ARCHITECTURE.md              # Цей документ — правила гри
├── README.md                    # Як запустити, стек, приклади виводу
├── .env.example                 # Всі змінні середовища з описами
├── pyproject.toml               # Poetry: залежності, налаштування
├── .gitignore                   # Виключення для Git
├── .gitattributes               # LF для *.sh (скрипт виконується в Linux-контейнері)
│
├── /infra                       # Локальна інфраструктура
│   └── /localstack
│       ├── docker-compose.local.yml   # LocalStack 4.14.0 (S3, DynamoDB)
│       └── init-aws.sh                # Бакет і таблиця, виконується автоматично (ready.d)
│
├── /src                         # Основний код
│   ├── /lambdas
│   │   ├── /transcribe
│   │   │   ├── __init__.py
│   │   │   └── handler.py       # L2 Lambda: транскрипція
│   │   ├── /score
│   │   │   ├── __init__.py
│   │   │   └── handler.py       # L4 Lambda: оцінка 0-100
│   │   └── /models
│   │       ├── __init__.py
│   │       └── events.py        # Pydantic-моделі подій
│   │
│   └── /utils
│       ├── __init__.py
│       ├── audio.py             # MP3/WAV → 16 кГц моно PCM, meeting_id з хешу файлу
│       ├── aws_config.py        # Спільні налаштування boto3 (LocalStack / AWS)
│       ├── logger.py            # Structured JSON-логи
│       ├── retry.py             # Exponential backoff
│       ├── s3_utils.py          # S3 download/upload (LocalStack)
│       └── dynamodb_utils.py    # DynamoDB idempotency
│
├── /tests                       # Всі тести
│   ├── /fixtures
│   │   └── tone.mp3             # 1 с, 44.1 кГц стерео — перевірка декодування
│   ├── /unit
│   │   ├── test_audio.py        # Декодування і meeting_id
│   │   ├── test_transcribe.py   # L2: успіх, помилки Azure, повтори, таймаут
│   │   ├── test_score.py        # L4: модель, повтори, схема відповіді, кеш
│   │   ├── test_retry.py        # Тести retry-логіки
│   │   ├── test_logger.py       # Тести логера
│   │   └── test_models.py       # Тести Pydantic-моделей
│   │
│   └── /integration
│       └── test_pipeline.py     # Повний пайплайн з LocalStack, повторний запуск з кешу
│
├── /demo                        # Демо-скрипти
│   ├── test_call.mp3            # Синтетичний sales-дзвінок, 82 с (голос Windows)
│   └── run_pipeline.py          # Запуск повного пайплайну локально
│
├── /scripts                     # Допоміжні скрипти
│   └── estimate_cost.py         # Розрахунок вартості дзвінка
│
└── /.github
    └── /workflows
        └── ci.yml               # Lint + unit + integration (LocalStack) на кожен push
```

---

## 2. Контракти між компонентами

### Вхід: Аудіофайл → L2 Transcribe

**Вхід:** MP3/WAV файл (локальний шлях)

**Трансформація в L2 Lambda:**
```python
# Вхід: шлях до аудіо
# Вихід: транскрипт (текст)

def handler(audio_path: str) -> dict:
    transcript = transcribe_audio(audio_path)
    return {
        "meeting_id": meeting_id_for(audio_path),  # SHA-256 вмісту файлу
        "transcript": transcript,
        "word_count": len(transcript.split()),
        "status": "transcribed"
    }
```

### L2 → L4 Score

**Вхід:** Транскрипт (текст)

**Трансформація в L4 Lambda:**
```python
# Вхід: транскрипт (текст)
# Вихід: score 0-100 + reasoning

SCORING_PROMPT = """
Analyze this sales call and score it 0-100 based on:
- Did the rep ask open questions?
- Did they handle objections?
- Was there a clear next step?

Transcript: {transcript}

Return JSON: {{"score": 0-100, "reasoning": "..."}}
"""

def handler(transcript: str) -> dict:
    # 1. Перевірка ідемпотентності в DynamoDB (по meeting_id)
    # 2. Виклик Groq API з retry
    # 3. Збереження результату в S3 + DynamoDB
    return {
        "meeting_id": meeting_id,
        "score": score,
        "reasoning": reasoning,
        "status": "scored"
    }
```

### S3 Структура (LocalStack)

```
s3://sales-score-dev/
├── audio/
│   └── {meeting_id}/
│       └── recording.mp3           # Оригінальне аудіо (опціонально)
├── transcripts/
│   └── raw/
│       └── {meeting_id}/
│           └── transcript.json     # L2 output
└── scores/
    └── {meeting_id}/
        └── score.json              # L4 output
```

### DynamoDB Таблиця (LocalStack)

**Таблиця:** `SalesScores`
- **PK:** `MEETING#{meeting_id}`
- **SK:** `SCORE#v1`
- **Attributes:** `score` (int), `reasoning` (str), `created_at` (str)
- **Idempotency:** Перед викликом Groq перевіряємо, чи є запис. Якщо є — повертаємо існуючий, не викликаємо API повторно.

---

## 3. Фази розробки з Acceptance Criteria

### Фаза 0 — Інфраструктура та середовище (2 години)

**Що робимо:**
1. `pyproject.toml` з Poetry: Python 3.12, залежності (`azure-cognitiveservices-speech`, `groq`, `boto3`, `pydantic`, `pytest`, `localstack`)
2. `.env.example` з описом змінних:
   ```
   AZURE_SPEECH_KEY=your_key_here
   AZURE_SPEECH_REGION=westeurope
   GROQ_API_KEY=your_key_here
   LOCALSTACK_ENDPOINT=http://localhost:4566
   ```
3. `.gitignore` (Python, venv, .env, LocalStack data)
4. `docker-compose.local.yml` з LocalStack (S3, DynamoDB)
5. `init-aws.sh` для створення бакетів і таблиць
6. `ARCHITECTURE.md` (цей документ)

**✅ Acceptance Criteria:**
- [ ] `poetry install` встановлює всі залежності без конфліктів
- [ ] `docker compose -f infra/localstack/docker-compose.local.yml up -d` піднімає LocalStack (init-aws.sh виконується автоматично)
- [ ] `docker exec localstack-main awslocal s3 ls` показує бакет `sales-score-dev`
- [ ] `docker exec localstack-main awslocal dynamodb list-tables` показує `SalesScores`
- [ ] `.env` створено з реальними ключами (Azure Speech, Groq)

**Оцінка часу:** 2 години

---

### Фаза 1 — L2 Lambda (Транскрипція) (3 години)

**Що робимо:**
1. `src/lambdas/transcribe/handler.py`: функція `transcribe_audio(audio_path)`
2. Інтеграція з Azure Speech SDK
3. Обробка помилок (невалідний формат, мережеві помилки)
4. `src/utils/logger.py`: structured JSON-логи
5. `src/utils/retry.py`: exponential backoff для Azure Speech
6. **Unit тести:** `test_transcribe.py` з моком Azure SDK

**✅ Acceptance Criteria:**
- [ ] `transcribe_audio("test_call.mp3")` повертає текст (не порожній)
- [ ] Логи в форматі JSON: `{"level":"INFO","component":"L2","msg":"Transcription completed","word_count":124}`
- [ ] Помилка мережі → retry 3 рази з exponential backoff → або успіх, або exception
- [ ] Unit тест проходить з моком Azure SDK

**Оцінка часу:** 3 години

---

### Фаза 2 — L4 Lambda (Scoring) (3 години)

**Що робимо:**
1. `src/lambdas/score/handler.py`: функція `score_transcript(transcript)`
2. Інтеграція з Groq API (`openai/gpt-oss-120b`; Llama 3.3 70B вимкнено в Groq 16.08.2026)
3. Structured output: JSON з полями `score` (int) і `reasoning` (str)
4. `src/utils/dynamodb_utils.py`: перевірка ідемпотентності, збереження результату
5. `src/utils/s3_utils.py`: збереження результату в S3
6. **Unit тести:** `test_score.py` з моком Groq API

**✅ Acceptance Criteria:**
- [ ] `score_transcript("Тестовий транскрипт")` повертає `{"score": 0-100, "reasoning": "..."}`
- [ ] JSON валідується Pydantic-моделлю
- [ ] Перед викликом Groq перевіряється DynamoDB (ідемпотентність)
- [ ] Результат зберігається в S3 (`scores/{meeting_id}/score.json`) і DynamoDB
- [ ] Помилка Groq API (rate limit) → retry 3 рази з exponential backoff

**Оцінка часу:** 3 години

---

### Фаза 3 — Повний пайплайн + LocalStack (2 години)

**Що робимо:**
1. `demo/run_pipeline.py`: скрипт, який об'єднує L2 і L4
2. Повний flow: аудіо → транскрипція → scoring → збереження в S3 + DynamoDB
3. `scripts/estimate_cost.py`: розрахунок вартості одного дзвінка
4. **Інтеграційний тест:** `tests/integration/test_pipeline.py` з LocalStack

**✅ Acceptance Criteria:**
- [ ] `poetry run python demo/run_pipeline.py --audio demo/test_call.mp3` виконується без помилок
- [ ] У S3 створено файли `transcripts/raw/{meeting_id}/transcript.json` і `scores/{meeting_id}/score.json`
- [ ] У DynamoDB створено запис з score
- [ ] Повторний запуск на тому ж файлі (той самий `meeting_id`) → **не викликає** ні Azure, ні Groq (ідемпотентність)
- [ ] `python scripts/estimate_cost.py` показує вартість <$0.05/дзвінок (за ціною Azure ~$1/год це дзвінки до ~3 хв; 5-хв дзвінок коштує ~$0.08 лише на Azure)
- [ ] Інтеграційний тест проходить

**Оцінка часу:** 2 години

---

### Фаза 4 — Документація та CI/CD (2 години)

**Що робимо:**
1. `README.md`: як встановити, налаштувати, запустити, приклад виводу
2. `.github/workflows/ci.yml`: lint (ruff) + test (pytest) на кожен push
3. Скріншоти терміналу з успішним запуском
4. Фінальний коміт і пуш у GitHub

**✅ Acceptance Criteria:**
- [ ] README містить:
  - Як отримати API-ключі (Azure Speech, Groq)
  - Як запустити LocalStack
  - Як запустити пайплайн
  - Приклад виводу (текст транскрипції, score, reasoning)
- [ ] CI pipeline зелений: ruff check → 0 помилок, pytest → всі тести проходять
- [ ] Репозиторій публічний, доступний за посиланням
- [ ] Рядок додано в резюме

**Оцінка часу:** 2 години

---

## 4. Загальна оцінка часу

| Фаза | Час | Кумулятивно |
| :--- | :--- | :--- |
| 0 — Інфраструктура | 2 год | 2 год |
| 1 — L2 Transcribe | 3 год | 5 год |
| 2 — L4 Score | 3 год | 8 год |
| 3 — Повний пайплайн | 2 год | 10 год |
| 4 — Документація + CI | 2 год | **12 год** |

**Реалістично:** 2 дні по 6 годин.

---

## 5. Що НЕ входить в scope (для ясності)

| Фіча | Чому не зараз | Коли |
| :--- | :--- | :--- |
| **L3 Sanitize (PII redaction, діаризація)** | Ускладнює MVP, не критично для демо | v2.0 |
| **EventBridge (події між Lambda)** | LocalStack підтримує, але це +2 год налаштувань | v1.1 |
| **Реальний деплой в AWS** | Потребує AWS-акаунту, кредитної картки | Коли буде офер |
| **Авторизація / Multi-tenancy** | Не потрібно для демо | v2.0 |
| **Діаризація (speaker identification)** | Azure Speech підтримує, але це ускладнює код | v1.2 |
| **Відео-демо** | Достатньо скріншотів | Опціонально |

---

## 6. Definition of Done для всього проєкту

- [ ] Всі 4 фази завершені з Acceptance Criteria
- [ ] `poetry install` встановлює залежності без помилок
- [ ] LocalStack піднімається, S3 + DynamoDB працюють
- [ ] Повний пайплайн (аудіо → текст → score) працює локально
- [ ] Ідемпотентність працює (повторний запуск не викликає Groq)
- [ ] Всі тести проходять (unit + integration)
- [ ] CI/CD зелений (ruff + pytest)
- [ ] README дозволяє сторонній людині підняти систему
- [ ] Рядок додано в резюме
- [ ] Репозиторій публічний на GitHub

---

## 7. Наступні кроки (що робити завтра)

```bash
# 1. Отримати API-ключі
# - Azure Speech: portal.azure.com → Create Speech Service → Keys
# - Groq: console.groq.com → API Keys

# 2. Встановити залежності
poetry install

# 3. Запустити LocalStack (бакет і таблиця створюються автоматично)
docker compose -f infra/localstack/docker-compose.local.yml up -d

# 4. Написати L2 Lambda
# src/lambdas/transcribe/handler.py

# 5. Протестувати L2 локально
poetry run python -c "from src.lambdas.transcribe.handler import transcribe_audio; print(transcribe_audio('demo/test_call.mp3'))"
```