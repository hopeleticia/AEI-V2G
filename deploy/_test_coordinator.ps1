Import-Module Posh-SSH
$piPassword = $env:AEI_PI_PASSWORD
if (-not $piPassword) { throw "Set AEI_PI_PASSWORD before running this script." }
$pw = ConvertTo-SecureString $piPassword -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("pi1", $pw)
$s = New-SSHSession -ComputerName 192.168.137.217 -Credential $cred -AcceptKey -Force -ConnectionTimeout 15 -ErrorAction Stop
# Run directly (not nohup) so we capture errors
$r = Invoke-SSHCommand -SessionId $s.SessionId -TimeOut 20 -Command "cd /home/pi1/aei-v2g && AEI_NODE_ROLE=lava-validator AEI_NODE_ID=pi1 AEI_MQTT_BROKER=192.168.137.217 python3 -m integration.coordinator --duration 5 --output /tmp/test_out.json 2>&1 | head -30"
Write-Host $r.Output
Remove-SSHSession -SessionId $s.SessionId | Out-Null
