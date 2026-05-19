Import-Module Posh-SSH
$piPassword = $env:AEI_PI_PASSWORD
if (-not $piPassword) { throw "Set AEI_PI_PASSWORD before running this script." }
$pw = ConvertTo-SecureString $piPassword -AsPlainText -Force
$nodes = @(
  @{ id="pi1"; user="pi1"; ip="100.112.171.127" },
  @{ id="pi2"; user="pi2"; ip="100.99.112.11" },
  @{ id="pi3"; user="pi3"; ip="100.94.93.69"  },
  @{ id="pi5"; user="pi5"; ip="100.84.220.4"  },
  @{ id="pi6"; user="pi6"; ip="100.79.78.93" }
)
foreach ($node in $nodes) {
  $cred = New-Object System.Management.Automation.PSCredential($node.user, $pw)
  $s = New-SSHSession -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 60 -ErrorAction Stop
  $r = Invoke-SSHCommand -SessionId $s.SessionId -Command "echo '=== $($node.id) ==='; tail -8 /tmp/aei_$($node.id).log 2>/dev/null || echo no_log; echo '---'"
  Write-Host $r.Output
  Remove-SSHSession -SessionId $s.SessionId | Out-Null
}
