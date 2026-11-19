# Core8-AI lead agent. No dependencies to install: the app is plain Node.
FROM node:22-alpine
WORKDIR /app
COPY package.json server.cjs ./
COPY lib ./lib
COPY public ./public
COPY tools ./tools
RUN mkdir /data && chown node:node /data
USER node
ENV NODE_ENV=production CORE8_PILOT_DATA=/data CORE8_PILOT_BIND=0.0.0.0 CORE8_PILOT_PORT=4180
VOLUME /data
EXPOSE 4180
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- --header="Host: $CORE8_PILOT_PUBLIC_HOST" http://127.0.0.1:4180/login.html >/dev/null || exit 1
CMD ["node", "server.cjs"]
