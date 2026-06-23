FROM node:20-slim

WORKDIR /app

COPY package.json .
RUN npm install --omit=dev

COPY index.js .

EXPOSE 3200

CMD ["node", "index.js"]
