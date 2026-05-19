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
$script = (Resolve-Path "deploy\_setup_venv.sh").Path
foreach ($node in $nodes) {
  Write-Host "=== $($node.id) ==="
  $cred = New-Object System.Management.Automation.PSCredential($node.user, $pw)
  try {
    $s    = New-SSHSession  -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 60 -ErrorAction Stop
    $sftp = New-SFTPSession -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 60 -ErrorAction Stop
    Set-SFTPItem -SessionId $sftp.SessionId -Path $script -Destination "/home/$($node.user)/" -Force
    Remove-SFTPSession -SessionId $sftp.SessionId | Out-Null

    $dns = Invoke-SSHCommand -SessionId $s.SessionId -TimeOut 30 -Command "grep -q '^nameserver ' /etc/resolv.conf || printf '$piPassword\n' | sudo -S sh -c 'printf `"nameserver 8.8.8.8\nnameserver 1.1.1.1\n`" > /etc/resolv.conf'"
    if ($dns.Error) { Write-Host "$($node.id): DNS preflight: $($dns.Error)" }

    $r = Invoke-SSHCommand -SessionId $s.SessionId -TimeOut 600 -Command "bash /home/$($node.user)/_setup_venv.sh"
    Write-Host "$($node.id): $($r.Output)"
    Remove-SSHSession -SessionId $s.SessionId | Out-Null
  } catch { Write-Host "$($node.id): FAILED - $($_.Exception.Message)" }
}
Write-Host "Done."
