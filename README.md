# AI Call Analyzer (Production-Ready)

Професійна система автоматичного аналізу та оцінки якості дзвінків sales-менеджерів за допомогою AI. Побудовано за стандартами Senior Engineering (4+ роки досвіду).

## 🚀 Основні можливості
- **Транскрибція (L2):** Надійна транскрибція довгих аудіо-файлів (1-10 хв) через Azure Speech Services (Continuous Recognition).
- **Оцінка (L4):** Глибокий аналіз дзвінка через Groq (Llama 3.3 70B) з наданням об'єктивної оцінки та аргументації.
- **Відмовостійкість:** Впроваджено Exponential Backoff з джиттером для всіх зовнішніх API.
- **Продуктова готовність:** Структуроване JSON-логування, типізація через Pydantic, повна підтримка LocalStack (S3, DynamoDB) для локальної розробки.
- **Ідемпотентність:** Повторні запити з тим самим ID не викликають платні API, дані беруться з кешу (DynamoDB).

## 🛠️ Стек технологій
- **Backend:** Python 3.12, Poetry
- **AI/LLM:** Groq API (Llama 3.3), Azure Speech SDK
- **Infrastructure (Local):** LocalStack (S3, DynamoDB), Docker Compose
- **Quality:** pytest, ruff (linting), GitHub Actions CI

## 📋 Початок роботи

### 1. Налаштування середовища
```bash
# Встановлення залежностей
poetry install

# Налаштування .env (використовуйте .env.example як шаблон)
# Потрібні ключі AZURE_SPEECH_KEY та GROQ_API_KEY
```

### 2. Запуск інфраструктури
```bash
# Запуск контейнерів LocalStack
docker-compose -f infra/localstack/docker-compose.local.yml up -d

# Ініціалізація бакетів та таблиць
# Для Linux/macOS:
chmod +x infra/localstack/init-aws.sh
./infra/localstack/init-aws.sh
```

### 3. Запуск аналізу
```bash
# Повний запуск пайплайну для аудіо-файлу
poetry run python demo/run_pipeline.py --audio "demo/test_call.mp3"
```

## 🧪 Тестування
```bash
# Запуск юніт-тестів
poetry run pytest tests/unit/

# Запуск інтеграційних тестів (потребує запущеного LocalStack)
poetry run pytest tests/integration/
```

## 📈 Оцінка вартості
```bash
poetry run python scripts/estimate_cost.py --minutes 5 --tokens 2000
```

Детальна архітектура описана в [ARCHITECTURE.md](./ARCHITECTURE.md).
