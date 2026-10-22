FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ATMET_HOME=/data
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN python -m pip install --no-cache-dir . && useradd --create-home --uid 10001 atmet && mkdir -p /data && chown atmet:atmet /data
USER atmet
VOLUME ["/data"]
EXPOSE 7310
ENTRYPOINT ["atmet-brain"]
CMD ["serve", "--host", "0.0.0.0", "--allow-network"]
