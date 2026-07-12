FROM node:22-alpine

WORKDIR /app

COPY package.json ./
COPY package-lock.json ./
RUN npm ci

COPY . .

RUN npm run build
RUN test -f /app/dist/index.html
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 5173

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173"]
