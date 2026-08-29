FROM nginx:1.25-alpine

# 替换默认站点配置
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY website/ /var/www/home/
COPY academy/ /var/www/academy/
COPY ai_interview/front/ /var/www/ai_interview/
COPY frontend/ /var/www/matchSys/
