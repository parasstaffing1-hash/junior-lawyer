FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:22-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL=/api/v1
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S juniorlawyer && adduser -S juniorlawyer -G juniorlawyer
COPY --from=builder --chown=juniorlawyer:juniorlawyer /app/.next/standalone ./
COPY --from=builder --chown=juniorlawyer:juniorlawyer /app/.next/static ./.next/static
USER juniorlawyer
EXPOSE 3000
CMD ["node", "server.js"]
