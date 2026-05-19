Import-Module Posh-SSH
$piPassword = $env:AEI_PI_PASSWORD
if (-not $piPassword) { throw "Set AEI_PI_PASSWORD before running this script." }
$pw = ConvertTo-SecureString $piPassword -AsPlainText -Force
$nodes = @(
  @{ id="pi1"; user="pi1"; ip="192.168.137.217" },
  @{ id="pi2"; user="pi2"; ip="192.168.137.246" },
  @{ id="pi3"; user="pi3"; ip="192.168.137.13"  },
  @{ id="pi5"; user="pi5"; ip="192.168.137.16"  },
  @{ id="pi6"; user="pi6"; ip="192.168.137.104" }
)
foreach ($node in $nodes) {
  Write-Host "=== $($node.id) ==="
  $cred = New-Object System.Management.Automation.PSCredential($node.user, $pw)
  $s = New-SSHSession -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 15 -ErrorAction Stop
  # Use "sudo python3 -m pip" to ensure packages go into THIS Python's path
  $r = Invoke-SSHCommand -SessionId $s.SessionId -TimeOut 300 -Command @'
sudo python3 -m pip install --break-system-packages -q paho-mqtt 'web3>=6.0.0'
python3 -c "import paho.mqtt.client; print('paho_ok')"
python3 -c "import web3; print('web3_ok')"
echo INSTALL_OK
'@
  Write-Host "$($node.id): $($r.Output)"
  Remove-SSHSession -SessionId $s.SessionId | Out-Null
}
Write-Host "Done."
