# Stage 1: build the React app.
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Django serves the API and the built app (WhiteNoise).
FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /app/frontend/dist frontend/dist
# Railway sets PORT. Threads let one instance serve another user while a plan waits on the APIs.
CMD gunicorn --chdir backend config.wsgi --threads 4 --timeout 60 --bind 0.0.0.0:${PORT:-8000}
