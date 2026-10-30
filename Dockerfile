# Build the browser app first.
FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json ./package.json
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Run FastAPI and serve the compiled React app from the same origin.
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMNILENS_SESSION_TTL=1800 \
    OMNILENS_MAX_UPLOAD_MB=25
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend-build /build/dist ./backend/static/
EXPOSE 8000
# Keep one worker: sessions intentionally live in this process's RAM.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
