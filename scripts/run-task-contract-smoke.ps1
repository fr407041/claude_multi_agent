param(
  [string]$ApiBase = 'http://127.0.0.1:18080',
  [int]$TimeoutSeconds = 900,
  [string]$ExpectedMarker = 'claude-multi-agent-repo-runtime-v2'
)

$ErrorActionPreference = 'Stop'
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("run_task_contract_smoke_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

function Save-Json($Path, $Value) {
  $Value | ConvertTo-Json -Depth 30 | Set-Content -Encoding utf8 $Path
}

function Invoke-PostTask($Payload, $Name) {
  $requestPath = Join-Path $TempDir "$Name-request.json"
  Save-Json $requestPath $Payload
  $raw = curl.exe -sS --max-time 30 -H 'Content-Type: application/json' --data-binary "@$requestPath" "$ApiBase/run-task" 2>&1
  if ($LASTEXITCODE -ne 0 -or $raw -notmatch '^\s*\{') {
    throw "POST /run-task failed: $raw"
  }
  $raw | Set-Content -Encoding utf8 (Join-Path $TempDir "$Name-initial.json")
  return $raw | ConvertFrom-Json
}

function Wait-Run($RunId, $Name) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds + 60)
  while ((Get-Date) -lt $deadline) {
    $raw = curl.exe -sS --max-time 20 "$ApiBase/runs/$RunId" 2>&1
    if ($LASTEXITCODE -eq 0 -and $raw -match '^\s*\{') {
      $raw | Set-Content -Encoding utf8 (Join-Path $TempDir "$Name-final.json")
      $parsed = $raw | ConvertFrom-Json
      if (@('succeeded','failed','timeout','interrupted') -contains $parsed.status) {
        return [ordered]@{ raw = $raw; parsed = $parsed }
      }
    }
    Start-Sleep -Seconds 5
  }
  throw "run timed out while polling: $RunId"
}

$healthRaw = curl.exe -sS --max-time 10 "$ApiBase/health" 2>&1
if ($LASTEXITCODE -ne 0) {
  throw "GET /health failed: $healthRaw"
}
$healthRaw | Set-Content -Encoding utf8 (Join-Path $TempDir 'health.json')

$markerInitial = Invoke-PostTask @{
  task = 'Runtime override marker check. Print the mounted repository runtime marker and do not run a real task.'
  timeout_seconds = 120
} 'marker'
$markerFinal = Wait-Run $markerInitial.run_id 'marker'

if ($markerFinal.raw -notmatch [regex]::Escape("RUNTIME_OVERRIDE_MARKER:$ExpectedMarker")) {
  throw "STALE_IMAGE_RUNTIME: /run-task is not executing the mounted repo runtime override. Mount ./agent-test-runtime/run_task.sh to /app/runtime/run_task.sh or rebuild the image. run_id=$($markerInitial.run_id)"
}

$contractInitial = Invoke-PostTask @{
  task = 'Return exact JSON only: {"ok":true,"repo":"fr407041/claude_multi_agent","contract":"exact_json"}'
  timeout_seconds = $TimeoutSeconds
} 'contract'
$contractFinal = Wait-Run $contractInitial.run_id 'contract'

$raw = $contractFinal.raw
$status = [string]$contractFinal.parsed.status
$resultText = [string]$contractFinal.parsed.result_text
$combined = "$raw`n$resultText"
$hasContractFailure = $combined -match 'TASK_OUTPUT_CONTRACT_FAILED'
$hasContractPass = $combined -match '"task_contract_status"\s*:\s*"pass"'
$hasNoThink = $combined -match 'Unknown command: /no_think'

if ($hasNoThink) {
  throw 'FALSE_SUCCESS_BLOCKED: output still contains Unknown command: /no_think'
}
if ($status -eq 'succeeded' -and -not $hasContractPass) {
  throw 'FALSE_SUCCESS_BLOCKED: run succeeded without task_contract_status=pass evidence'
}
if ($status -ne 'succeeded' -and -not $hasContractFailure) {
  throw 'UNCLASSIFIED_CONTRACT_FAILURE: failed run did not expose TASK_OUTPUT_CONTRACT_FAILED'
}

[ordered]@{
  pass = $true
  run_id = $contractInitial.run_id
  status = $status
  contract_enforced = $true
  evidence_dir = $TempDir
} | ConvertTo-Json -Depth 10
