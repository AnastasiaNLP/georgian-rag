#!/bin/bash

envsubst < /etc/alertmanager/alertmanager.yml.template > /etc/alertmanager/alertmanager.yml

echo "Alertmanager config created with environment variables"
cat /etc/alertmanager/alertmanager.yml

# Start alertmanager
exec /bin/alertmanager "$@"
