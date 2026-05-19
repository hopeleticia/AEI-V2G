Import-Module Posh-SSH
$piPassword = $env:AEI_PI_PASSWORD
if (-not $piPassword) { throw "Set AEI_PI_PASSWORD before running this script." }
$pw = ConvertTo-SecureString $piPassword -AsPlainText -Force
$nodes = @(
  @{ id="pi2"; user="pi2"; ip="192.168.137.246" },
  @{ id="pi3"; user="pi3"; ip="192.168.137.13"  },
  @{ id="pi6"; user="pi6"; ip="192.168.137.104" }
)
foreach ($node in $nodes) {
  Write-Host "=== $($node.id) ==="
  $cred = New-Object System.Management.Automation.PSCredential($node.user, $pw)
  try {
    $s = New-SSHSession -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 20 -ErrorAction Stop
    # Install directly into the system dist-packages dir that is already in sys.path
    $r = Invoke-SSHCommand -SessionId $s.SessionId -TimeOut 300 -Command @'
set -e
TARGET=/usr/local/lib/python3.13/dist-packages
sudo python3 -m pip install --break-system-packages --target $TARGET paho-mqtt 2>&1 | tail -3
sudo python3 -m pip install --break-system-packages --target $TARGET 'web3>=6.0.0' 2>&1 | tail -3
python3 -c "import paho.mqtt.client; print('paho_ok')" || { echo PAHO_FAIL; exit 1; }
python3 -c "import web3; print('web3_ok')" || { echo WEB3_FAIL; exit 1; }
echo ALL_OK
'@
    Write-Host "$($node.id): $($r.Output)"
    Remove-SSHSession -SessionId $s.SessionId | Out-Null
  } catch { Write-Host "$($node.id): OFFLINE - $($_.Exception.Message)" }
}
Write-Host "Done."
