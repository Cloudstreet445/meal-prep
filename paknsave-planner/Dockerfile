FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

EXPOSE 5001

# Generation can take 60-90s (4 Claude API calls) — give uvicorn a long timeout
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "5001", "--timeout-keep-alive", "120"]
