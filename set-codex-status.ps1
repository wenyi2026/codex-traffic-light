param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("idle", "done", "complete", "completed", "running", "thinking", "attention", "approval", "error", "blocked", "green", "yellow", "red")]
  [string]$Status,

  [string]$Message = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StatusFile = Join-Path $Root "codex_status.json"
$DistStatusFile = Join-Path (Join-Path $Root "dist") "codex_status.json"

$Map = @{
  green = "idle"
  done = "idle"
  complete = "idle"
  completed = "idle"
  yellow = "running"
  thinking = "running"
  red = "attention"
  approval = "attention"
  error = "attention"
  blocked = "attention"
}

$Normalized = if ($Map.ContainsKey($Status)) { $Map[$Status] } else { $Status }

$DefaultMessages = @{
  idle = "Task completed; Codex is idle."
  running = "Task is running normally, or Codex is thinking."
  attention = "Needs approval, error, or human intervention."
}

if ([string]::IsNullOrWhiteSpace($Message)) {
  $Message = $DefaultMessages[$Normalized]
}

$Payload = [ordered]@{
  status = $Normalized
  message = $Message
  updated_at = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
}

$TempFile = "$StatusFile.tmp"
$Payload | ConvertTo-Json -Depth 3 | Set-Content -Path $TempFile -Encoding UTF8
Move-Item -Path $TempFile -Destination $StatusFile -Force
if (Test-Path (Split-Path -Parent $DistStatusFile)) {
  $DistTempFile = "$DistStatusFile.tmp"
  $Payload | ConvertTo-Json -Depth 3 | Set-Content -Path $DistTempFile -Encoding UTF8
  Move-Item -Path $DistTempFile -Destination $DistStatusFile -Force
}
Write-Host "Codex status set to $Normalized -> $StatusFile"
