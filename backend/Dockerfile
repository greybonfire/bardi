FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN python -m pip install --no-cache-dir uv==0.12.8

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY backend ./backend

EXPOSE 8000

CMD ["python", "backend/manage.py", "runserver", "0.0.0.0:8000", "--settings=bardi.settings.development"]
