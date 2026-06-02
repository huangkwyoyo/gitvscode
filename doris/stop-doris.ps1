$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot
docker compose -f .\docker-compose.yml down
