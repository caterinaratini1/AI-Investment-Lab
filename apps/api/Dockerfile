FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-runtime-lock.txt ./requirements-runtime-lock.txt
COPY alembic.ini ./alembic.ini
COPY packages/domain ./packages/domain
COPY packages/data_providers ./packages/data_providers
COPY packages/db ./packages/db
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker

RUN pip install --no-cache-dir -r requirements-runtime-lock.txt \
    && pip install --no-cache-dir --no-deps --no-build-isolation \
        ./packages/domain ./packages/data_providers ./packages/db ./apps/api ./apps/worker

USER 65534

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn ai_investment_lab.api.main:app --host 0.0.0.0 --port 8000"]
