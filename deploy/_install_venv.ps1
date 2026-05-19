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
  try {
    $s = New-SSHSession -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 20 -ErrorAction Stop
    $venv = "/home/$($node.user)/aei-venv"
    $r = Invoke-SSHCommand -SessionId $s.SessionId -TimeOut 300 -Command "python3 -m venv $venv && $venv/bin/pip install -q paho-mqtt 'web3>=6.0.0' 2>&1 | tail -3 && $venv/bin/python3 -c 'import paho.mqtt.client, web3; print(\"paho+web3 OK\")' && echo VENV_READY"
    Write-Host "$($node.id): $($r.Output)"
    Remove-SSHSession -SessionId $s.SessionId | Out-Null
  } catch { Write-Host "$($node.id): OFFLINE - $($_.Exception.Message)" }
}
Write-Host "Done."
