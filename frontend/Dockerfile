FROM nginx:1.27-alpine

# Copy static assets
COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/app.js /usr/share/nginx/html/app.js
COPY frontend/styles.css /usr/share/nginx/html/styles.css

# Nginx config to proxy /api to backend
COPY frontend/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
