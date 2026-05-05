FROM nginx:alpine
COPY static/index.html /usr/share/nginx/html/
COPY manifest.json /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000