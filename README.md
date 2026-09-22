# AI Call Analyzer

Система автоматичного аналізу та оцінки якості дзвінків sales-менеджерів за допомогою AI: аудіо → транскрипція → оцінка 0-100 з аргументацією → збереження в S3 і DynamoDB (локально через LocalStack).

## 🚀 Основні можливості
- **Транскрибція (L2):** аудіо-файли 1-10 хв (MP3, WAV, FLAC, OGG) через Azure Speech Services (Continuous Recognition). Будь-який формат спершу декодується в 16 кГц моно PCM, який приймає Azure.
- **Оцінка (L4):** аналіз дзвінка через Groq (модель за замовчуванням `openai/gpt-oss-120b`, змінюється через `GROQ_MODEL`). Відповідь моделі валідується Pydantic-схемою (score 0-100).
- **Відмовостійкість:** Exponential Backoff з джиттером лише для тимчасових збоїв (мережа, rate limit, помилки сервісу). Невірний ключ або файл — одразу зрозуміла помилка, без повторів.
- **Ідемпотентність:** `meeting_id` — хеш вмісту аудіо-файлу. Повторний запуск на тому ж записі бере транскрипт з S3 і оцінку з DynamoDB, платні API не викликаються.
- **Структуроване JSON-логування**, типізація через Pydantic, LocalStack (S3, DynamoDB) для локальної розробки.

## 🛠️ Стек технологій
- **Backend:** Python 3.12, Poetry
- **AI/LLM:** Groq API (`openai/gpt-oss-120b`), Azure Speech SDK, miniaudio (декодування аудіо)
- **Infrastructure (Local):** LocalStack 4.14 (S3, DynamoDB), Docker Compose
- **Quality:** pytest, ruff (linting), GitHub Actions CI (lint + unit + integration з LocalStack)

## 📋 Початок роботи

### 1. Налаштування середовища
```bash
# Встановлення залежностей
poetry install

# Налаштування .env з шаблону (Windows: copy .env.example .env)
cp .env.example .env
# Далі вписати в .env ключі AZURE_SPEECH_KEY та GROQ_API_KEY
```

Де взяти ключі:
- **Azure Speech:** portal.azure.com → Create a resource → Speech service → Keys and Endpoint (ключ + регіон → `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`)
- **Groq:** console.groq.com → API Keys → Create API Key (`GROQ_API_KEY`)

### 2. Запуск інфраструктури
```bash
# Запуск LocalStack. Бакет sales-score-dev і таблиця SalesScores
# створюються автоматично скриптом infra/localstack/init-aws.sh
docker compose -f infra/localstack/docker-compose.local.yml up -d

# Перевірка, що ресурси створено
docker exec localstack-main awslocal s3 ls
docker exec localstack-main awslocal dynamodb list-tables
```

LocalStack закріплено на версії `4.14.0`: з 23.03.2026 новіші образи `localstack/localstack` вимагають auth token облікового запису LocalStack, а 4.14 — останній реліз, що працює без нього.

### 3. Запуск аналізу
```bash
# Повний запуск пайплайну для аудіо-файлу
poetry run python demo/run_pipeline.py --audio "demo/test_call.mp3"
```

`demo/test_call.mp3` — синтетичний англомовний sales-дзвінок (82 с), згенерований вбудованим голосом Windows (Microsoft Zira).

Формат виводу:
```
==================================================
FINAL RESULT FOR MEETING: <meeting_id: 32 hex-символи, хеш аудіо>
==================================================
Transcript: <текст дзвінка від Azure Speech>
Score: <0-100>/100
Reasoning: <пояснення оцінки від моделі>
Source: <api — перший запуск | cache — повторний>
==================================================
```

При помилці скрипт друкує `CRITICAL ERROR: <тип>: <причина>` і завершується з кодом 1.

## 🧪 Тестування
```bash
# Юніт-тести (без мережі і ключів)
poetry run pytest tests/unit/

# Інтеграційний тест (потребує запущеного LocalStack; Azure і Groq замокані)
poetry run pytest tests/integration/
```

## 📈 Оцінка вартості
```bash
poetry run python scripts/estimate_cost.py --minutes 5 --tokens 2000
```

Детальна архітектура описана в [ARCHITECTURE.md](./ARCHITECTURE.md).
