#!/usr/bin/env bash
# Render build step: install everything and build the React app.
set -o errexit

pip install -r backend/requirements.txt

cd frontend
npm ci
npm run build
cd ..

cd backend
python manage.py collectstatic --no-input