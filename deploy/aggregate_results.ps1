param(
  [string]$OutputFile = "reports/cluster_metrics.json"
)

Import-Module Posh-SSH -ErrorAction Stop

$nodes = @(
  @{ id="pi1"; user="pi1"; ip="100.112.171.127" },
  @{ id="pi2"; user="pi2"; ip="100.99.112.11" },
  @{ id="pi3"; user="pi3"; ip="100.94.93.69"  },
  @{ id="pi5"; user="pi5"; ip="100.84.220.4"  },
  @{ id="pi6"; user="pi6"; ip="100.79.78.93" }
)

$piPassword = $env:AEI_PI_PASSWORD
if (-not $piPassword) { throw "Set AEI_PI_PASSWORD before running this script." }
$pw = ConvertTo-SecureString $piPassword -AsPlainText -Force
$results = @{}

foreach ($node in $nodes) {
  Write-Host "Collecting from $($node.id) ($($node.ip))..."
  $cred = New-Object System.Management.Automation.PSCredential($node.user, $pw)
  try {
    $s = New-SSHSession -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 60 -ErrorAction Stop
    # Fetch metrics JSON
    $r = Invoke-SSHCommand -SessionId $s.SessionId -Command "cat ~/aei-v2g/reports/$($node.id)_metrics.json 2>/dev/null || echo '{}'"
    $results[$node.id] = $r.Output | ConvertFrom-Json -ErrorAction SilentlyContinue
    # Fetch last 5 lines of run log
    $log = Invoke-SSHCommand -SessionId $s.SessionId -Command "tail -5 /tmp/aei_$($node.id).log 2>/dev/null"
    Write-Host "  log: $($log.Output)"
    # Fetch chain tail (last hash for cross-node verification)
    $chain = Invoke-SSHCommand -SessionId $s.SessionId -Command "tail -1 ~/aei-v2g/data/$($node.id)_chain.jsonl 2>/dev/null | sed -n 's/.*\""hash\"": \""\([0-9a-f]*\)\"".*/\1/p' | cut -c1-16"
    Write-Host "  chain tail: $($chain.Output)"
    Remove-SSHSession -SessionId $s.SessionId | Out-Null
  } catch {
    Write-Warning "$($node.id): $($_.Exception.Message)"
    $results[$node.id] = $null
  }
}

$combined = @{
  collected_at = (Get-Date -Format "o")
  nodes        = $results
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$outPath = Join-Path $projectRoot $OutputFile
$combined | ConvertTo-Json -Depth 10 | Set-Content $outPath
Write-Host ""
Write-Host "Saved combined results → $outPath"
