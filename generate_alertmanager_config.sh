#!/bin/bash
# Generate alertmanager.yml from template with .env variables

if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file with your credentials."
    exit 1
fi

source .env

if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "⚠️  Warning: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env"
    echo "Alertmanager will not send Telegram notifications."
fi

envsubst < monitoring/alertmanager.yml.template > monitoring/alertmanager.yml

echo "✅ Generated monitoring/alertmanager.yml with your credentials"
