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

if ($Build) {
  docker build -t $Image $projectRoot
}

New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot "reports") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot "data") | Out-Null

docker run --rm `
  -v "${projectRoot}/reports:/app/reports" `
  -v "${projectRoot}/data:/app/data:ro" `
  $Image `
  python -m eval.run_journal_study `
    --config $Config `
    --duration $DurationSeconds `
    --output-dir $OutputDir

python -m eval.validate_journal_results `
  --report-dir $OutputDir `
  --output (Join-Path $OutputDir "VALIDATION_DEFENSE.md")

Write-Host "Docker experiment artifacts written to $OutputDir"
