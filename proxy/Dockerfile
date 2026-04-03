FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx redis
COPY server.py .
EXPOSE 4001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "4001"]
