FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt requirements.in requirements-lock.txt ./
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt && pip check
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
