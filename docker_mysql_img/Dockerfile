FROM mysql:8.4

# 初始化脚本（仅在 /var/lib/mysql 为空时按文件名顺序执行）
COPY docker_mysql_img/init/init.sql /docker-entrypoint-initdb.d/01-matchsys.sql
COPY ai_interview/back/database/init_mysql.sql /docker-entrypoint-initdb.d/02-ai-interview.sql
