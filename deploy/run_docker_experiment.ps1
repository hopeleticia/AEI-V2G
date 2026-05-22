param(
  [string]$Image = "aei-v2g:local",
  [string]$Config = "config/corridor_config.yaml",
  [int]$DurationSeconds = 86400,
  [string]$OutputDir = "",
  [switch]$Build
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDir) {
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $OutputDir = "reports/docker_experiment_$stamp"
}

$configPath = Join-Path $projectRoot $Config
if (-not (Test-Path -LiteralPath $configPath)) {
  throw "Config not found: $Config"
}

$envPath = Join-Path $projectRoot ".env"
if (Test-Path -LiteralPath $envPath) {
  Get-Content -LiteralPath $envPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
      return
    }
    $key, $value = $line.Split("=", 2)
    if (-not [Environment]::GetEnvironmentVariable($key, "Process")) {
      [Environment]::SetEnvironmentVariable($key, $value.Trim("`"", "'"), "Process")
    }
  }
}

if ($Build) {
  docker build -t $Image $projectRoot
}

New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot "reports") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot "data") | Out-Null

docker run --rm `
  -e AEI_ETH_RPC_URL="$env:AEI_ETH_RPC_URL" `
  -e AEI_ETH_ACCOUNT="$env:AEI_ETH_ACCOUNT" `
  -e AEI_ETH_PRIVATE_KEY="$env:AEI_ETH_PRIVATE_KEY" `
  -e AEI_CREDIT_LEDGER_ADDRESS="$env:AEI_CREDIT_LEDGER_ADDRESS" `
  -e AEI_ETH_GAS_PRICE_WEI="$env:AEI_ETH_GAS_PRICE_WEI" `
  -v "${projectRoot}/reports:/app/reports" `
  -v "${projectRoot}/data:/app/data:ro" `
  $Image `
  python -m eval.run_journal_study `
    --config $Config `
    --duration $DurationSeconds `
    --output-dir $OutputDir

$pythonCmd = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py" }
& $pythonCmd -m eval.validate_journal_results `
  --report-dir $OutputDir `
  --output (Join-Path $OutputDir "VALIDATION_DEFENSE.md")

Write-Host "Docker experiment artifacts written to $OutputDir"
