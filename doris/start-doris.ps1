$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot
docker compose -f .\docker-compose.yml up -d
docker compose -f .\docker-compose.yml ps
