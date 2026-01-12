FROM mysql:8.4

# 初始化脚本（仅在 /var/lib/mysql 为空时执行）
COPY docker_mysql_img/init/ /docker-entrypoint-initdb.d/
