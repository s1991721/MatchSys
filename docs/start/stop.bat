@echo off

docker compose -f docker-compose.yml -f docker-compose.nvidia.yml down

if %errorlevel% neq 0 (
    docker compose down
)