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
  Write-Host "=== Fixing DNS + installing deps on $($node.id) ==="
  $cred = New-Object System.Management.Automation.PSCredential($node.user, $pw)
  $s = New-SSHSession -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 15 -ErrorAction Stop
  # Add Google DNS if not already there, then install
  $r = Invoke-SSHCommand -SessionId $s.SessionId -TimeOut 300 -Command @"
grep -q '8.8.8.8' /etc/resolv.conf || echo 'nameserver 8.8.8.8' | sudo tee -a /etc/resolv.conf
grep -q '1.1.1.1' /etc/resolv.conf || echo 'nameserver 1.1.1.1' | sudo tee -a /etc/resolv.conf
python3 -c 'import paho.mqtt.client' 2>/dev/null && echo PAHO_ALREADY || pip3 install --break-system-packages -q paho-mqtt 2>&1 | tail -2
python3 -c 'import web3' 2>/dev/null && echo WEB3_ALREADY || pip3 install --break-system-packages -q web3 2>&1 | tail -2
echo DEPS_OK
"@
  Write-Host "$($node.id): $($r.Output)"
  Remove-SSHSession -SessionId $s.SessionId | Out-Null
}
Write-Host "Done."
