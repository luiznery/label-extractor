FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra app
COPY app ./app
COPY samples ./samples
COPY eval ./eval
ENV GRADIO_SERVER_NAME=0.0.0.0
EXPOSE 7860
CMD ["uv", "run", "--no-dev", "--extra", "app", "python", "app/app.py"]
