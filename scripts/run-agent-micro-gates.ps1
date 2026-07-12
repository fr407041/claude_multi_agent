param(
  [string]$ApiBase = 'http://127.0.0.1:18080',
  [int]$TimeoutSeconds = 1800,
  [switch]$SkipGateF
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$RunSetId = 'micro-gates-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$RunSetDir = Join-Path $Root "agent-test-runs/$RunSetId"
New-Item -ItemType Directory -Force -Path $RunSetDir | Out-Null

function Save-Json($Path, $Value) {
  $Value | ConvertTo-Json -Depth 30 | Set-Content -Encoding utf8 $Path
}

function Invoke-JsonPost($Uri, $BodyPath) {
  $attempts = 0
  while ($attempts -lt 20) {
    $attempts++
    try {
      $healthRaw = curl.exe -sS --max-time 10 "$ApiBase/health" 2>&1
      if ($LASTEXITCODE -ne 0 -or $healthRaw -notmatch '"healthy"\s*:\s*true') {
        Start-Sleep -Seconds 5
        continue
      }
    } catch {
      Start-Sleep -Seconds 5
      continue
    }
    $raw = curl.exe -sS --max-time 30 -H 'Content-Type: application/json' --data-binary "@$BodyPath" $Uri 2>&1
    if ($LASTEXITCODE -eq 0 -and $raw -match '^\s*\{') {
      return [ordered]@{ raw = $raw; attempts = $attempts; parsed = ($raw | ConvertFrom-Json) }
    }
    Start-Sleep -Seconds 5
  }
  throw "POST failed after $attempts attempts: $raw"
}

function Invoke-JsonGet($Uri) {
  $raw = curl.exe -sS --max-time 20 $Uri 2>&1
  if ($LASTEXITCODE -ne 0 -or $raw -notmatch '^\s*\{') {
    throw "GET failed: $raw"
  }
  [ordered]@{ raw = $raw; parsed = ($raw | ConvertFrom-Json) }
}

function Wait-Run($RunId, $GateDir) {
  $pollDir = Join-Path $GateDir 'polls'
  New-Item -ItemType Directory -Force -Path $pollDir | Out-Null
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds + 60)
  $poll = 0
  $last = $null
  while ((Get-Date) -lt $deadline) {
    $poll++
    $now = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    try {
      $status = Invoke-JsonGet "$ApiBase/runs/$RunId"
      $status.raw | Set-Content -Encoding utf8 (Join-Path $pollDir "status-$now.json")
      $last = $status.parsed
      Write-Host "gate poll=$poll run=$RunId status=$($last.status) return_code=$($last.return_code)"
      if (@('succeeded','failed','timeout','interrupted') -contains $last.status) {
        return $last
      }
    } catch {
      $_.Exception.Message | Set-Content -Encoding utf8 (Join-Path $pollDir "poll-error-$now.txt")
      Write-Host "gate poll=$poll run=$RunId api_poll_error=$($_.Exception.Message)"
    }
    Start-Sleep -Seconds 10
  }
  throw "run polling timed out: $RunId"
}

function Get-Task($Gate) {
  switch ($Gate) {
    'A' {
      return @'
Micro gate A: tool execution only.

Create ./ptt-stock-live/proof.txt containing exactly:
TOOL_EXECUTED_OK

Then print exactly TOOL_EXECUTED_OK and nothing else.
'@
    }
    'B' {
      return @'
Micro gate B: PTT Stock homepage connectivity only.

Use live tools inside this container. Do not use mock data.
Fetch https://www.ptt.cc/bbs/Stock/index.html yourself using curl or python.
Save the raw response body to ./ptt-stock-live/index.html.
Then print only JSON with:
{"http_ok": true or false, "bytes": number, "contains_stock_board_marker": true or false}
'@
    }
    'C' {
      return @'
Micro gate C: parse 5 PTT Stock article URLs only.

Use live tools inside this container. Do not use mock data and do not use caller-provided crawler code.
Fetch PTT Stock list pages yourself from https://www.ptt.cc/bbs/Stock/index.html.
Parse exactly 5 unique article URLs matching https://www.ptt.cc/bbs/Stock/...html.
Save them to ./ptt-stock-live/urls.json as either ["url1", ...] or {"urls": ["url1", ...]}.
Then print exactly the contents of ./ptt-stock-live/urls.json and nothing else.
'@
    }
    'D' {
      return @'
Micro gate D: parse one PTT Stock article body only.

Use live tools inside this container. Do not use mock data.
Fetch PTT Stock yourself, choose the newest valid article, fetch its article page, and parse title, url, author, date, and body.
Use article title and body only; ignore push comments.
Save ./ptt-stock-live/article.json with fields title, url, author, date, body.
Then print exactly the contents of ./ptt-stock-live/article.json and nothing else.
'@
    }
    'E' {
      return @'
Micro gate E: 3-article stock stance analysis.

Use live tools inside this container. Do not use mock data and do not use caller-provided crawler code.
Fetch PTT Stock yourself, collect exactly 3 unique analyzable article URLs, parse title/body only, and analyze mentioned stocks.
Save raw/parsed artifacts and save ./ptt-stock-live/final.json.
Final answer must be exactly final.json and nothing else.
final.json must include source_board, fetched_at_utc, article_count=3, articles[], stocks[], limitations.
Each stock must include ticker_or_name, stance, confidence, bullish_evidence, bearish_evidence, neutral_evidence, article_urls.
'@
    }
    'F' {
      return @'
Micro gate F: 20-article PTT Stock full task.

Use live tools inside this container. Do not use mock data and do not use caller-provided crawler code.
Fetch PTT Stock yourself, collect exactly 20 unique analyzable article URLs, parse title/body only, and analyze mentioned stocks.
Save raw/parsed artifacts and save ./ptt-stock-live/final.json.
Final answer must be exactly final.json and nothing else.
final.json must include source_board, fetched_at_utc, article_count=20, articles[], stocks[], limitations.
Each stock must include ticker_or_name, stance, confidence, bullish_evidence, bearish_evidence, neutral_evidence, article_urls.
'@
    }
  }
}

$summary = [ordered]@{
  run_set_id = $RunSetId
  run_set_dir = $RunSetDir
  api_base = $ApiBase
  started_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  gates = @()
  pass = $false
}

try {
  $healthRaw = curl.exe -sS --max-time 15 "$ApiBase/health" 2>&1
  $healthRaw | Set-Content -Encoding utf8 (Join-Path $RunSetDir 'health.json')
  if ($LASTEXITCODE -ne 0 -or $healthRaw -notmatch '"healthy"\s*:\s*true') {
    throw "health failed: $healthRaw"
  }

  $gates = @('A','B','C','D','E')
  if (-not $SkipGateF) { $gates += 'F' }

  foreach ($gate in $gates) {
    $gateDir = Join-Path $RunSetDir "gate-$gate"
    New-Item -ItemType Directory -Force -Path $gateDir | Out-Null
    Write-Host "=== Gate $gate ==="

    $payload = [ordered]@{
      task = Get-Task $gate
      timeout_seconds = $TimeoutSeconds
    }
    $requestPath = Join-Path $gateDir 'request.json'
    Save-Json $requestPath $payload

    $initial = Invoke-JsonPost "$ApiBase/run-task" $requestPath
    $initial.raw | Set-Content -Encoding utf8 (Join-Path $gateDir 'initial-response.json')
    $runId = $initial.parsed.run_id

    $final = Wait-Run $runId $gateDir
    Save-Json (Join-Path $gateDir 'final-status.json') $final

    $localRunDir = Join-Path $Root "agent-test-runs/$runId"
    $verifierRaw = powershell -ExecutionPolicy Bypass -File (Join-Path $ScriptDir 'verify-agent-micro-gate.ps1') -Gate $gate -RunDir $localRunDir 2>&1
    $verifierExit = $LASTEXITCODE
    $verifierRaw | Set-Content -Encoding utf8 (Join-Path $gateDir 'verifier-result.json')
    $verifier = $null
    try { $verifier = ($verifierRaw | Out-String | ConvertFrom-Json) } catch {}

    $gateResult = [ordered]@{
      gate = $gate
      run_id = $runId
      api_status = $final.status
      return_code = $final.return_code
      run_dir = $localRunDir
      verifier_exit_code = $verifierExit
      verifier_pass = ($verifierExit -eq 0)
      verifier_result_path = (Join-Path $gateDir 'verifier-result.json')
    }
    $summary.gates += $gateResult
    Save-Json (Join-Path $RunSetDir 'run-summary.json') $summary

    if ($final.status -ne 'succeeded' -or $final.return_code -ne 0 -or $verifierExit -ne 0) {
      $summary.pass = $false
      $summary.failed_gate = $gate
      $summary.finished_at_utc = (Get-Date).ToUniversalTime().ToString('o')
      Save-Json (Join-Path $RunSetDir 'run-summary.json') $summary
      Write-Host "Gate $gate FAILED. Stopping subsequent gates."
      exit 1
    }
  }

  $summary.pass = $true
  $summary.finished_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  Save-Json (Join-Path $RunSetDir 'run-summary.json') $summary
  Write-Host "All requested gates passed."
  exit 0
} catch {
  $summary.pass = $false
  $summary.error = $_.Exception.Message
  $summary.finished_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  Save-Json (Join-Path $RunSetDir 'run-summary.json') $summary
  Write-Host "Micro gates runner failed: $($_.Exception.Message)"
  exit 1
}
