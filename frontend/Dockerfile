FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY tsconfig.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
