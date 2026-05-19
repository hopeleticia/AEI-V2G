param(
  [int]$DurationSeconds = 600,
  [switch]$SkipDeploy,
  [switch]$StopOnly
)

# ── Node definitions ────────────────────────────────────────────────────────
$ethRpcUrl = if ($env:AEI_ETH_RPC_URL) { $env:AEI_ETH_RPC_URL } else { "https://purechainnode.com:8547" }
$nodes = @(
  @{ id="pi1"; user="pi1"; ip="192.168.137.217"; role="lava-validator";    stations="";                mqttBroker="192.168.137.217"; ethAccount=$env:AEI_PI1_ACCOUNT; ethKey=$env:AEI_PI1_PRIVATE_KEY },
  @{ id="pi2"; user="pi2"; ip="192.168.137.246"; role="station-validator"; stations="station_a,station_b"; mqttBroker="192.168.137.217"; ethAccount=$env:AEI_PI2_ACCOUNT; ethKey=$env:AEI_PI2_PRIVATE_KEY },
  @{ id="pi3"; user="pi3"; ip="192.168.137.13";  role="station-validator"; stations="station_c";           mqttBroker="192.168.137.217"; ethAccount=$env:AEI_PI3_ACCOUNT; ethKey=$env:AEI_PI3_PRIVATE_KEY },
  @{ id="pi5"; user="pi5"; ip="192.168.137.16";  role="rsu-observer";      stations="";                mqttBroker="192.168.137.217"; ethAccount=$env:AEI_PI5_ACCOUNT; ethKey=$env:AEI_PI5_PRIVATE_KEY },
  @{ id="pi6"; user="pi6"; ip="192.168.137.104"; role="grid-observer";     stations="";                mqttBroker="192.168.137.217"; ethAccount=$env:AEI_PI6_ACCOUNT; ethKey=$env:AEI_PI6_PRIVATE_KEY }
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$sshOpts = "-o StrictHostKeyChecking=no -o ConnectTimeout=10"
$remoteDir = "~/aei-v2g"

# ── Helper: run SSH command ──────────────────────────────────────────────────
function Invoke-SSH($node, $cmd) {
  $target = "$($node.user)@$($node.ip)"
  ssh $sshOpts.Split(" ") $target $cmd
}

# ── STOP mode ────────────────────────────────────────────────────────────────
if ($StopOnly) {
  foreach ($node in $nodes) {
    Write-Host "Stopping $($node.id)..."
    Invoke-SSH $node "pkill -f 'python -m integration.coordinator' 2>/dev/null; docker stop mosquitto 2>/dev/null; echo stopped"
  }
  exit 0
}

# ── DEPLOY: rsync code to each Pi ───────────────────────────────────────────
if (-not $SkipDeploy) {
  foreach ($node in $nodes) {
    Write-Host "Deploying to $($node.id) ($($node.ip))..."
    # Create remote dir
    Invoke-SSH $node "mkdir -p $remoteDir/reports $remoteDir/data/grid_profiles $remoteDir/data"
    # rsync source → Pi (exclude heavy output dirs and caches)
    $rsyncArgs = @(
      "-az", "--delete",
      "--exclude=__pycache__", "--exclude=*.pyc", "--exclude=.git",
      "--exclude=reports/journal_study*", "--exclude=reports/*.json",
      "-e", "ssh $sshOpts",
      "$projectRoot/",
      "$($node.user)@$($node.ip):$remoteDir/"
    )
    rsync @rsyncArgs
    if ($LASTEXITCODE -ne 0) {
      Write-Warning "rsync failed for $($node.id) — trying scp fallback..."
      # Pack and scp if rsync unavailable
      $tmp = [System.IO.Path]::GetTempFileName() + ".tar.gz"
      Push-Location $projectRoot
      tar -czf $tmp --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' `
        --exclude='reports/journal_study*' .
      Pop-Location
      scp $sshOpts.Split(" ") $tmp "$($node.user)@$($node.ip):/tmp/aei-v2g.tar.gz"
      Invoke-SSH $node "cd ~ && rm -rf aei-v2g && mkdir aei-v2g && tar -xzf /tmp/aei-v2g.tar.gz -C aei-v2g && rm /tmp/aei-v2g.tar.gz"
      Remove-Item $tmp
    }
    # Install Python deps
    Write-Host "  Installing deps on $($node.id)..."
    Invoke-SSH $node "cd $remoteDir && pip3 install -q -r requirements.txt"
    Write-Host "  $($node.id) ready."
  }
}

# ── START mosquitto broker on pi1 first ─────────────────────────────────────
$broker = $nodes | Where-Object { $_.role -eq "lava-validator" } | Select-Object -First 1
Write-Host "Starting MQTT broker on $($broker.id)..."
Invoke-SSH $broker @"
  pkill -f mosquitto 2>/dev/null; sleep 1
  nohup mosquitto -c $remoteDir/deploy/mosquitto.conf > /tmp/mosquitto.log 2>&1 &
  sleep 2 && echo "broker_pid=\$(pgrep mosquitto)"
"@

# ── START each node ──────────────────────────────────────────────────────────
foreach ($node in $nodes) {
  $stationEnv = if ($node.stations) { "AEI_STATION_IDS=$($node.stations)" } else { "" }
  $runCmd = @"
    export AEI_NODE_ROLE=$($node.role)
    export AEI_NODE_ID=$($node.id)
    export AEI_MQTT_BROKER=$($node.mqttBroker)    export AEI_ETH_RPC_URL=$ethRpcUrl
    export AEI_ETH_ACCOUNT=$($node.ethAccount)
    export AEI_ETH_PRIVATE_KEY=$($node.ethKey)    $stationEnv
    cd $remoteDir
    mkdir -p reports data
    nohup python3 -m integration.coordinator \
      --config config/corridor_config.yaml \
      --duration $DurationSeconds \
      --output reports/$($node.id)_metrics.json \
      --chain data/$($node.id)_chain.jsonl \
      > /tmp/aei_$($node.id).log 2>&1 &
    echo "started pid=\$!"
"@
  Write-Host "Starting $($node.id) (role=$($node.role))..."
  Invoke-SSH $node $runCmd
}

Write-Host ""
Write-Host "All nodes started.  Duration: ${DurationSeconds}s"
Write-Host "Monitor logs:  ssh <piN>@<ip> 'tail -f /tmp/aei_<id>.log'"
Write-Host "Collect results:  .\deploy\aggregate_results.ps1"
