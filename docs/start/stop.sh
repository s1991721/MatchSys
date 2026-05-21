#!/bin/bash

docker compose \
-f docker-compose.yml \
-f docker-compose.nvidia.yml \
down 2>/dev/null || docker compose down