$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "frontend")

if (-not (Test-Path "node_modules")) {
    npm install
}

npm run dev
