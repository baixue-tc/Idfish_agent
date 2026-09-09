FROM python:3.14-slim
WORKDIR /app
RUN apt-get update && apt-get install -y g++ && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN pip install uv
RUN uv sync --frozen
COPY . .
CMD ["uv","run","uvicorn","app.main:app","--host","0.0.0.0","--port","8001"]
