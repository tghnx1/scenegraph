FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY prisma.config.ts ./
COPY prisma ./prisma

EXPOSE 5555

CMD ["npx", "prisma", "migrate", "deploy"]
