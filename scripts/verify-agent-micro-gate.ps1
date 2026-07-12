param(
  [Parameter(Mandatory = $true)][ValidateSet('A','B','C','D','E','F')][string]$Gate,
  [Parameter(Mandatory = $true)][string]$RunDir
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Verifier = Join-Path $ScriptDir 'verify_agent_micro_gate.py'

if (-not (Test-Path $Verifier)) {
  [ordered]@{
    pass = $false
    gate = $Gate
    run_dir = $RunDir
    checked_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    fail_reasons = @("python verifier missing: $Verifier")
    details = [ordered]@{}
  } | ConvertTo-Json -Depth 20
  exit 1
}

$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) {
  $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
  [ordered]@{
    pass = $false
    gate = $Gate
    run_dir = $RunDir
    checked_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    fail_reasons = @("python interpreter not found")
    details = [ordered]@{}
  } | ConvertTo-Json -Depth 20
  exit 1
}

& $python.Source $Verifier --gate $Gate --run-dir $RunDir --json
exit $LASTEXITCODE
