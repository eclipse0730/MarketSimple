# Cloud Run 용 경량 이미지. GitHub 워크플로를 트리거만 하므로 Chrome·pandas 불필요.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Cloud Run 은 $PORT 로 들어온다(기본 8080). uvicorn 을 그 포트에 바인딩.
ENV PORT=8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
