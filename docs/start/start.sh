#!/bin/bash

if command -v nvidia-smi >/dev/null 2>&1; then
  docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up -d
else
  docker compose up -d
fi