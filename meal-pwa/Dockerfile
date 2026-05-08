FROM nginx:alpine

ARG VERSION=dev

COPY static/index.html /usr/share/nginx/html/
COPY static/style.css /usr/share/nginx/html/
COPY static/app.js /usr/share/nginx/html/
COPY manifest.json /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN sed -i "s/__VERSION__/$VERSION/g" /usr/share/nginx/html/index.html

EXPOSE 3000