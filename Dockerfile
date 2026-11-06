FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HUB_DATA_DIR=/data
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY firmware/esp32-companion/dist ./firmware/esp32-companion/dist
RUN pip install --no-cache-dir . && useradd --uid 10001 --user-group --no-create-home hub && mkdir /data && chown hub:hub /data
USER 10001:10001
VOLUME ["/data"]
EXPOSE 10000 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)" || exit 1
CMD ["solarman-hub", "serve"]
