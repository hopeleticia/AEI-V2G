param(
  [int]$DurationSeconds = 600,
  [int]$GridStartMinute = 0
)

Import-Module Posh-SSH
$piPassword = $env:AEI_PI_PASSWORD
if (-not $piPassword) { throw "Set AEI_PI_PASSWORD before launching the cluster." }
$pw = ConvertTo-SecureString $piPassword -AsPlainText -Force
$mqttBroker = "100.112.171.127"
$ethRpcUrl = if ($env:AEI_ETH_RPC_URL) { $env:AEI_ETH_RPC_URL } else { "https://purechainnode.com:8547" }

$nodes = @(
  @{ id="pi1"; user="pi1"; ip="100.112.171.127"; role="lava-validator";
     stations=""; mqttBroker="127.0.0.1"; ethAccount=$env:AEI_PI1_ACCOUNT;
     ethKey=$env:AEI_PI1_PRIVATE_KEY },
  @{ id="pi2"; user="pi2"; ip="100.99.112.11"; role="station-validator";
     stations="station_a,station_b"; mqttBroker=$mqttBroker; ethAccount=$env:AEI_PI2_ACCOUNT;
     ethKey=$env:AEI_PI2_PRIVATE_KEY },
  @{ id="pi3"; user="pi3"; ip="100.94.93.69";  role="station-validator";
     stations="station_c"; mqttBroker=$mqttBroker; ethAccount=$env:AEI_PI3_ACCOUNT;
     ethKey=$env:AEI_PI3_PRIVATE_KEY },
  @{ id="pi5"; user="pi5"; ip="100.84.220.4";  role="rsu-observer";
     stations=""; mqttBroker=$mqttBroker; ethAccount=$env:AEI_PI5_ACCOUNT;
     ethKey=$env:AEI_PI5_PRIVATE_KEY },
  @{ id="pi6"; user="pi6"; ip="100.79.78.93"; role="grid-observer";
     stations=""; mqttBroker=$mqttBroker; ethAccount=$env:AEI_PI6_ACCOUNT;
     ethKey=$env:AEI_PI6_PRIVATE_KEY }
)

# ── 1. Start mosquitto broker on pi1 ──────────────────────────────────────
$broker = $nodes[0]
Write-Host "Starting MQTT broker on $($broker.id)..."
$cred = New-Object System.Management.Automation.PSCredential($broker.user, $pw)
$s = New-SSHSession -ComputerName $broker.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 60 -ErrorAction Stop
$brokerResult = Invoke-SSHCommand -SessionId $s.SessionId -Command "printf '$piPassword\n' | sudo -S systemctl stop mosquitto 2>/dev/null || true; pkill mosquitto 2>/dev/null || true; sleep 1; rm -f /tmp/mosquitto.log; MOSQUITTO=`$(command -v mosquitto || echo /usr/sbin/mosquitto); nohup `$MOSQUITTO -c /home/$($broker.user)/aei-v2g/deploy/mosquitto.conf > /tmp/mosquitto.log 2>&1 & sleep 2 && echo BROKER_OK"
Write-Host "  $($brokerResult.Output)"
if ($brokerResult.Error) { Write-Host "  ERROR: $($brokerResult.Error)" }
Remove-SSHSession -SessionId $s.SessionId | Out-Null
Start-Sleep -Seconds 3

# ── 2. Launch each node ───────────────────────────────────────────────────
foreach ($node in $nodes) {
  Write-Host "Starting $($node.id) (role=$($node.role))..."
  $cred = New-Object System.Management.Automation.PSCredential($node.user, $pw)
  $s = New-SSHSession -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 60 -ErrorAction Stop

  $base = "/home/$($node.user)/aei-v2g"
  $stationExport = if ($node.stations) { "export AEI_STATION_IDS=$($node.stations)" } else { "" }
  Invoke-SSHCommand -SessionId $s.SessionId -Command "pkill -f '[i]ntegration.coordinator' 2>/dev/null || true; sleep 1" | Out-Null

  $cmd = @"
export AEI_NODE_ROLE=$($node.role)
export AEI_NODE_ID=$($node.id)
export AEI_MQTT_BROKER=$($node.mqttBroker)
export AEI_GRID_START_MINUTE=$GridStartMinute
export AEI_ETH_RPC_URL=$ethRpcUrl
export AEI_ETH_ACCOUNT=$($node.ethAccount)
export AEI_ETH_PRIVATE_KEY=$($node.ethKey)
$stationExport
VENV=/home/$($node.user)/aei-venv
PYTHON=`$VENV/bin/python3
[ -f "`$PYTHON" ] || PYTHON=python3
cd $base
rm -f /tmp/aei_$($node.id).log
nohup `$PYTHON -m integration.coordinator \
  --config config/corridor_config.yaml \
  --duration $DurationSeconds \
  --output reports/$($node.id)_metrics.json \
  --chain data/$($node.id)_chain.jsonl \
  > /tmp/aei_$($node.id).log 2>&1 &
echo "pid=`$!"
"@
  $cmd = $cmd -replace "`r`n", "`n"
  $r = Invoke-SSHCommand -SessionId $s.SessionId -Command $cmd
  Write-Host "  $($node.id): $($r.Output)"
  if ($r.Error) { Write-Host "  $($node.id) ERROR: $($r.Error)" }
  Remove-SSHSession -SessionId $s.SessionId | Out-Null
}

Write-Host ""
Write-Host "Cluster running for ${DurationSeconds}s."
Write-Host "Collect results: .\deploy\aggregate_results.ps1"
