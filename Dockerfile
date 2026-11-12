# One Python image for the simulator, gateway, API and assistant.
# docker-compose picks what each container runs.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sbc ./sbc

CMD ["uvicorn", "sbc.api:app", "--host", "0.0.0.0", "--port", "8000"]
