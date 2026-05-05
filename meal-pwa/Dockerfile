FROM nginx:alpine
COPY static/index.html /usr/share/nginx/html/
COPY static/style.css /usr/share/nginx/html/
COPY static/app.js /usr/share/nginx/html/
COPY manifest.json /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000