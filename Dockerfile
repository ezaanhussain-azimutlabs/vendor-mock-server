FROM python:3.13-slim

WORKDIR /app

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser server.py .

ENV MOCK_PORT=8088 \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8088

ENTRYPOINT ["python", "server.py"]
