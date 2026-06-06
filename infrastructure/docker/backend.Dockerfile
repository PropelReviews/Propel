FROM python:3.12-slim

WORKDIR /app

# Placeholder until FastAPI app is scaffolded.
# Keeps the container running so docker-compose up succeeds.
CMD ["python", "-c", "import time; print('Propel backend placeholder — waiting for app code'); [time.sleep(3600) or True for _ in iter(int, 1)]"]
