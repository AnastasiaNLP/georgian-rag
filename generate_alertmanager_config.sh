#!/bin/bash
# Generate alertmanager.yml from template with .env variables

if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    exit 1
fi

# Export переменных БЕЗ выполнения .env как скрипта
export $(grep -v '^#' .env | grep -v '^$' | xargs)

if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "⚠️  Warning: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"
fi

envsubst < monitoring/alertmanager.yml.template > monitoring/alertmanager.yml

echo "✅ Generated monitoring/alertmanager.yml with your credentials"
