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
  # Fix DNS persistently via systemd-resolved, then install in same session before it can reset
  $r = Invoke-SSHCommand -SessionId $s.SessionId -TimeOut 300 -Command @'
set -e
# Persist DNS via systemd-resolved drop-in
sudo mkdir -p /etc/systemd/resolved.conf.d
echo -e '[Resolve]\nDNS=8.8.8.8 1.1.1.1\nFallbackDNS=9.9.9.9' | sudo tee /etc/systemd/resolved.conf.d/dns.conf
sudo systemctl restart systemd-resolved 2>/dev/null || true
# Also write resolv.conf directly (works immediately)
echo -e 'nameserver 8.8.8.8\nnameserver 1.1.1.1' | sudo tee /etc/resolv.conf
# Test DNS then install
python3 -c "import socket; socket.getaddrinfo('pypi.org',443)" && echo DNS_OK
pip3 install --break-system-packages -q paho-mqtt 2>&1 | tail -3
pip3 install --break-system-packages -q 'web3>=6.0.0' 2>&1 | tail -3
python3 -c "import paho.mqtt.client; print('paho OK')"
python3 -c "import web3; print('web3 OK')"
echo ALL_DONE
'@
  Write-Host "$($node.id): $($r.Output)"
  Remove-SSHSession -SessionId $s.SessionId | Out-Null
}
Write-Host "Done."
