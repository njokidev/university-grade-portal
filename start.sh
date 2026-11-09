#!/usr/bin/env bash
# Render start step: prepare the database, load demo data if empty, start the server.
set -o errexit

cd backend
python manage.py migrate --no-input
python manage.py seed_demo --if-empty
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2