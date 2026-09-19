# syntax=docker/dockerfile:1

FROM python:3.14-slim

ENV TERM=xterm-256color \
    LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    TODO_DB_DIR=/data

WORKDIR /src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY todo.py api.py ./

VOLUME /data

# По умолчанию — API. TUI переопределит CMD через compose.
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]