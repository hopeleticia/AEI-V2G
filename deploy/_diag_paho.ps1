Import-Module Posh-SSH
$piPassword = $env:AEI_PI_PASSWORD
if (-not $piPassword) { throw "Set AEI_PI_PASSWORD before running this script." }
$pw = ConvertTo-SecureString $piPassword -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("pi3", $pw)
$s = New-SSHSession -ComputerName 192.168.137.13 -Credential $cred -AcceptKey -Force -ConnectionTimeout 20 -ErrorAction Stop
# Verbose install to see exactly where packages go
$r = Invoke-SSHCommand -SessionId $s.SessionId -TimeOut 60 -Command @'
echo "=== pip target ==="
sudo python3 -m pip install --break-system-packages paho-mqtt 2>&1
echo "=== find paho ==="
find /usr /root /home -name "__init__.py" -path "*/paho/*" 2>/dev/null
echo "=== sys.path ==="
python3 -c "import sys; [print(p) for p in sys.path]"
echo "=== import test ==="
python3 -c "import paho.mqtt.client; print('PAHO_WORKS')" 2>&1
'@
Write-Host $r.Output
Remove-SSHSession -SessionId $s.SessionId | Out-Null
