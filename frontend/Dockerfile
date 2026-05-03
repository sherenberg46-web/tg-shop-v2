## Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# Declare build-time arg so Railway passes VITE_API_URL into the Vite build
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

## Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["/bin/sh", "-c", "nginx -g 'daemon off;'"]
