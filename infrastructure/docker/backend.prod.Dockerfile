# Production image for the FastAPI API (shipped to ECR -> ECS Fargate).
# Build context is the `backend/` directory:
#   docker build -f infrastructure/docker/backend.prod.Dockerfile -t propel-api backend
#
# Unlike backend.Dockerfile (dev), this bakes the application code into the
# image and runs uvicorn WITHOUT --reload.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# ECS has no logConfiguration (no CloudWatch); stdout is not collected.
# Observability is exported to PostHog by the app (OpenTelemetry traces).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
