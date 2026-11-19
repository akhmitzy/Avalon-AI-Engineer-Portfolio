# Build context: repository root.
FROM python:3.12-slim AS build
WORKDIR /src
COPY python/ ./python/
COPY shared/phi_patterns.json ./python/dxreview/phi/patterns.json
RUN pip install --no-cache-dir build && python -m build --wheel ./python --outdir /wheels

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DXREVIEW_PROVIDER=offline
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir "$(ls /wheels/*.whl)[anthropic,bedrock]" && rm -rf /wheels
USER 10001
EXPOSE 8080
CMD ["uvicorn", "dxreview.api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
