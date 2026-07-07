FROM nginx:1.25-alpine

# 替换默认站点配置
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY website/ /var/www/home/
COPY frontend/ /var/www/matchSys/
