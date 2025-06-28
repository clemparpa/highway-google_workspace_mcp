#!/bin/sh
set -e  # Arrêt immédiat en cas d'erreur

docker buildx build --platform linux/amd64,linux/arm64 -t clemparpa/highway-google-workspace-mcp:latest . --push