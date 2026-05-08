FROM nginx:alpine

ARG VERSION=dev
ARG API_HOST=192.168.1.85:8000

COPY static/index.html /usr/share/nginx/html/
COPY static/style.css /usr/share/nginx/html/
COPY static/app.js /usr/share/nginx/html/
COPY static/sw.js /usr/share/nginx/html/
COPY manifest.json /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN sed -i "s/__VERSION__/$VERSION/g" /usr/share/nginx/html/index.html && \
    sed -i "s/__API_HOST__/$API_HOST/g" /etc/nginx/conf.d/default.conf

EXPOSE 3000