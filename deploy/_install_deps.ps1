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
  Write-Host "=== Installing deps on $($node.id) ==="
  $cred = New-Object System.Management.Automation.PSCredential($node.user, $pw)
  $s = New-SSHSession -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 15 -ErrorAction Stop
  $r = Invoke-SSHCommand -SessionId $s.SessionId -TimeOut 300 -Command "pip3 install --break-system-packages -q paho-mqtt web3 PyYAML 2>&1 | tail -3 && echo DEPS_OK"
  Write-Host "$($node.id): $($r.Output)"
  Remove-SSHSession -SessionId $s.SessionId | Out-Null
}
Write-Host "All deps installed."
