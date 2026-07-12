[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$runId = 'run-{0}-{1}' -f ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')), ([guid]::NewGuid().ToString('N').Substring(0,8))
$bootstrap = Join-Path $root "logs\$runId\bootstrap"
New-Item -ItemType Directory -Force -Path $bootstrap | Out-Null

function Invoke-Logged([string]$Name, [scriptblock]$Command) {
    $stdout = Join-Path $bootstrap "$Name.stdout.log"
    $stderr = Join-Path $bootstrap "$Name.stderr.log"
    $started = [DateTime]::UtcNow
    # Windows PowerShell promotes native stderr progress (used by Compose) to
    # ErrorRecord when ErrorActionPreference is Stop. Capture it as evidence
    # and decide strictly from the native exit code instead.
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Command 1> $stdout 2> $stderr
    $code = $LASTEXITCODE
    $ErrorActionPreference = $oldPreference
    [pscustomobject]@{ name=$Name; started_at=$started.ToString('o'); finished_at=[DateTime]::UtcNow.ToString('o'); exit_code=$code; stdout=$stdout; stderr=$stderr } |
        ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $bootstrap "$Name.json")
    if ($code -ne 0) { throw "$Name failed with exit code $code; see $stderr" }
}

try {
    Invoke-Logged 'docker-compose-build' { docker compose build }
    Invoke-Logged 'docker-compose-up' { docker compose up -d }
    $healthy = $false
    for ($i=0; $i -lt 18; $i++) {
        $state = docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' multi-agent-claude-live-validator 2>$null
        if ($state -eq 'healthy') { $healthy = $true; break }
        if ($state -eq 'unhealthy' -or $state -eq 'exited') { break }
        Start-Sleep -Seconds 5
    }
    if (-not $healthy) {
        docker compose logs --no-color *> (Join-Path $bootstrap 'container-failure.log')
        throw 'container did not become healthy'
    }
    Invoke-Logged 'python-py-compile' { docker compose exec -T claude-live-validator python3 -m py_compile scripts/live_validation.py scripts/probe_provider_diagnostic.py }
    Invoke-Logged 'upstream-verify-install' { docker compose exec -T claude-live-validator python3 scripts/verify_install.py --strict --json }
    Invoke-Logged 'upstream-validate-spec' { docker compose exec -T claude-live-validator python3 scripts/validate_ai_company_spec.py docs/ai_specs/ai-company-release-readiness-strict-demo.json }
    Invoke-Logged 'live-validation' { docker compose exec -T -e RUN_ID=$runId claude-live-validator python3 scripts/live_validation.py }
    docker compose logs --no-color *> (Join-Path $bootstrap 'container.log')
    Write-Host "PASS run_id=$runId"
    Write-Host "Summary: $root\results\$runId\run-summary.json"
} catch {
    docker compose logs --no-color *> (Join-Path $bootstrap 'container.log') 2>$null
    $resultDir = Join-Path $root "results\$runId"
    New-Item -ItemType Directory -Force -Path $resultDir | Out-Null
    $failure = $_.Exception.Message
    $summaryPath = Join-Path $resultDir 'run-summary.json'
    $reportPath = Join-Path $resultDir 'final-report.md'
    if (-not (Test-Path $summaryPath)) {
      [ordered]@{
        run_id = $runId
        status = 'FAILED'
        live_mode = $true
        mock_used = $false
        provider = 'http://192.168.100.112:11435'
        model = 'qwen3-coder:30b'
        finished_at = [DateTime]::UtcNow.ToString('o')
        exit_code = 1
        failure_reason = $failure
        bootstrap_logs_path = $bootstrap
      } | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 $summaryPath
      @("# Live Validation FAILED", '', "- Run ID: ``$runId``", "- Exit code: ``1``", "- Failure: $failure", "- Bootstrap logs: ``$bootstrap``") |
          Set-Content -Encoding utf8 $reportPath
    }
    Write-Error "FAILED run_id=$runId $($_.Exception.Message)"
    exit 1
}
