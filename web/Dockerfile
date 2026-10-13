# Built from the repository root (pnpm workspace): docker build -f web/Dockerfile .
FROM node:24-alpine AS build
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY web/package.json web/
COPY office-addin/package.json office-addin/
RUN npm install -g "$(node -p "require('./package.json').packageManager")" \
    && pnpm install --frozen-lockfile --filter analekh-web
COPY web web
RUN pnpm --filter analekh-web build

FROM nginx:1.27-alpine
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/web/dist /usr/share/nginx/html
