FROM python:3.12-slim

RUN apt-get update && apt-get install -y nodejs npm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prisma ./prisma/
COPY app ./app/
COPY data ./data/
COPY .env .
COPY scripts ./scripts/

RUN npx prisma@5.17.0 generate

EXPOSE 3000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
