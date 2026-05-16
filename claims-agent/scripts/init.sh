#!/bin/bash
set -e
echo "=== claims-agent init ==="

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — please fill in your API keys"
fi

python manage.py migrate
python manage.py init_admin
python manage.py import_seed_data
python manage.py import_from_readonly
echo "Init complete."
