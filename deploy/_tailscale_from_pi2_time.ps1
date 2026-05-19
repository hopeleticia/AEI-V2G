param(
  [string]$AuthKey = "",
  [switch]$InstallOnly
)

Import-Module Posh-SSH

$pwPlain = $env:AEI_PI_PASSWORD
if (-not $pwPlain) { throw "Set AEI_PI_PASSWORD before running this script." }
$pw = ConvertTo-SecureString $pwPlain -AsPlainText -Force

$timeSource = @{ id="pi2"; user="pi2"; ip="192.168.137.246" }
$targets = @(
  @{ id="pi1"; user="pi1"; ip="192.168.137.217" },
  @{ id="pi3"; user="pi3"; ip="192.168.137.13"  },
  @{ id="pi5"; user="pi5"; ip="192.168.137.16"  },
  @{ id="pi6"; user="pi6"; ip="192.168.137.104" }
)

function New-PiSession($node) {
  $cred = New-Object System.Management.Automation.PSCredential($node.user, $pw)
  New-SSHSession -ComputerName $node.ip -Credential $cred -AcceptKey -Force -ConnectionTimeout 60 -ErrorAction Stop
}

Write-Host "Reading UTC time from $($timeSource.id)..."
$sourceSession = New-PiSession $timeSource
$timeResult = Invoke-SSHCommand -SessionId $sourceSession.SessionId -TimeOut 30 -Command "date -u '+%Y-%m-%d %H:%M:%S'"
Remove-SSHSession -SessionId $sourceSession.SessionId | Out-Null

if ($timeResult.ExitStatus -ne 0 -or -not $timeResult.Output) {
  throw "Could not read UTC time from $($timeSource.id): $($timeResult.Error)"
}

$sourceUtc = [string]$timeResult.Output[0]
Write-Host "Using pi2 UTC: $sourceUtc"

foreach ($node in $targets) {
  Write-Host "=== $($node.id) ==="
  try {
    $session = New-PiSession $node
    $remote = @"
set -e
printf '$pwPlain\n' | sudo -S date -u -s '$sourceUtc' >/dev/null
if ! grep -q '^nameserver ' /etc/resolv.conf; then
  printf '$pwPlain\n' | sudo -S sh -c 'printf "nameserver 8.8.8.8\nnameserver 1.1.1.1\n" > /etc/resolv.conf' >/dev/null 2>&1
fi
printf 'date_utc='; date -u '+%Y-%m-%dT%H:%M:%SZ'
if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
printf 'install='; command -v tailscale >/dev/null && echo ok || echo missing
current_ip=`$(tailscale ip -4 2>/dev/null | head -1 || true)
if [ -n "`$current_ip" ]; then
  printf 'tailscale_ip=%s\n' "`$current_ip"
  printf 'status='; tailscale status --self 2>/dev/null | head -1
  exit 0
fi
"@

    if (-not $InstallOnly) {
      if (-not $AuthKey) {
        throw "Pass -AuthKey or use -InstallOnly."
      }
      $remote += "`nprintf '$pwPlain\n' | sudo -S tailscale up --auth-key=$AuthKey --hostname=$($node.id)-aei-v2g >/dev/null"
      $remote += "`nprintf 'tailscale_ip='; tailscale ip -4 2>/dev/null | head -1"
      $remote += "`nprintf 'status='; tailscale status --self 2>/dev/null | head -1"
    }

    $result = Invoke-SSHCommand -SessionId $session.SessionId -TimeOut 420 -Command $remote
    $result.Output | ForEach-Object { Write-Host $_ }
    if ($result.Error) { $result.Error | Select-String -Pattern 'auth-key' -NotMatch | ForEach-Object { Write-Host $_ } }
    Remove-SSHSession -SessionId $session.SessionId | Out-Null
  } catch {
    Write-Host "$($node.id): FAILED - $($_.Exception.Message)"
  }
}

Write-Host "Done."
