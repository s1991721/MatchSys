@echo off

where nvidia-smi >nul 2>nul

if %errorlevel%==0 (
    docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up -d
) else (
    docker compose up -d
)