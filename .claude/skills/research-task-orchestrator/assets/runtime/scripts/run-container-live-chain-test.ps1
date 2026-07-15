param(
  [string]$SourceRoot = '',
  [string]$RunsRoot = '',
  [string]$RuntimeScript = '',
  [string]$ContainerName = 'claude-sdk-agent-test',
  [string]$Image = 'multi-agent-claude-router:local',
  [int]$ApiHostPort = 58080,
  [string]$OllamaBaseUrl = 'http://192.168.100.112:11435',
  [string]$ModelName = 'qwen3-coder:30b',
  [string]$RuntimeOverrideId = 'manual-sdk-test-v1',
  [int]$MarkerTimeoutSeconds = 120,
  [int]$LiveTimeoutSeconds = 1200,
  [int]$PollIntervalSeconds = 10,
  [ValidateSet('minimal','skill-visible','skill-lite','skill','artifact-lite','site-lite','skill-heavy','all')]
  [string]$LiveGateMode = 'all',
  [switch]$RequireFabPolicyPreflight,
  [string]$FabAgentHostRuntimeDir = '',
  [switch]$SkipContainerStart,
  [switch]$KeepContainer
)

$ErrorActionPreference = 'Stop'

function Resolve-AbsolutePath([string]$PathValue, [string]$DefaultValue) {
  $chosen = if ([string]::IsNullOrWhiteSpace($PathValue)) { $DefaultValue } else { $PathValue }
  if (-not (Test-Path -LiteralPath $chosen)) {
    throw "path not found: $chosen"
  }
  return (Resolve-Path -LiteralPath $chosen).Path
}

function Save-Json($Path, $Value) {
  $parent = Split-Path -Parent $Path
  if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  $Value | ConvertTo-Json -Depth 50 | Set-Content -Encoding utf8 $Path
}

function Save-Text($Path, [string]$Value) {
  $parent = Split-Path -Parent $Path
  if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  $Value | Set-Content -Encoding utf8 $Path
}

function Add-Step($Name, $Status, $Detail, $Extra = @{}) {
  $script:Steps += [ordered]@{
    name = $Name
    status = $Status
    detail = $Detail
    timestamp = (Get-Date).ToUniversalTime().ToString('o')
    extra = $Extra
  }
}

function Invoke-NativeCurl([string[]]$Arguments) {
  $oldPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $raw = & curl.exe @Arguments 2>&1
    $exit = $LASTEXITCODE
    return [ordered]@{
      exit_code = $exit
      body = [string]($raw -join "`n")
    }
  } finally {
    $ErrorActionPreference = $oldPreference
  }
}

function Invoke-CurlJsonGet([string]$Url, [string]$OutPath, [int]$MaxTime = 30) {
  $result = Invoke-NativeCurl @('-sS','--max-time',"$MaxTime",$Url)
  $raw = [string]$result.body
  $exit = [int]$result.exit_code
  Save-Text $OutPath $raw
  if ($exit -ne 0 -or $raw -notmatch '^\s*[\{\[]') {
    throw "GET failed url=$Url exit=$exit body=$raw"
  }
  return $raw | ConvertFrom-Json
}

function Invoke-CurlJsonPost([string]$Url, $Payload, [string]$Name, [int]$MaxTime = 30) {
  $requestPath = Join-Path $EvidenceDir "$Name-request.json"
  $responsePath = Join-Path $EvidenceDir "$Name-initial.json"
  Save-Json $requestPath $Payload
  $attempts = @()
  for ($attempt = 1; $attempt -le 6; $attempt++) {
    $result = Invoke-NativeCurl @('-sS','--max-time',"$MaxTime",'-H','Content-Type: application/json','--data-binary',"@$requestPath",$Url)
    $raw = [string]$result.body
    $exit = [int]$result.exit_code
    $attempts += [ordered]@{ attempt = $attempt; exit_code = $exit; body = $raw; timestamp = (Get-Date).ToUniversalTime().ToString('o') }
    Save-Text $responsePath $raw
    Save-Json (Join-Path $EvidenceDir "$Name-post-attempts.json") $attempts
    if ($exit -eq 0 -and $raw -match '^\s*\{') {
      return $raw | ConvertFrom-Json
    }
    Start-Sleep -Seconds ([Math]::Min(10, 2 * $attempt))
  }
  $last = $attempts[-1]
  throw "POST failed url=$Url exit=$($last.exit_code) body=$($last.body)"
}

function Wait-Run([string]$RunId, [string]$Name, [int]$TimeoutSeconds) {
  $polls = @()
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds + 30)
  while ((Get-Date) -lt $deadline) {
    $result = Invoke-NativeCurl @('-sS','--max-time','30',"$ApiBase/runs/$RunId")
    $raw = [string]$result.body
    $exit = [int]$result.exit_code
    $pollEntry = [ordered]@{
      timestamp = (Get-Date).ToUniversalTime().ToString('o')
      exit_code = $exit
      body = $raw
    }
    $polls += $pollEntry
    if ($exit -eq 0 -and $raw -match '^\s*\{') {
      $parsed = $raw | ConvertFrom-Json
      if (@('succeeded','failed','timeout','interrupted') -contains $parsed.status) {
        Save-Text (Join-Path $EvidenceDir "$Name-final.json") $raw
        Save-Json (Join-Path $EvidenceDir "$Name-polls.json") $polls
        return [ordered]@{ raw = $raw; parsed = $parsed }
      }
    }
    Start-Sleep -Seconds $PollIntervalSeconds
  }
  Save-Json (Join-Path $EvidenceDir "$Name-polls.json") $polls
  throw "run polling timed out name=$Name run_id=$RunId"
}

function Convert-RunDirToHostPath($RunDir, $RunId) {
  $text = [string]$RunDir
  if (-not [string]::IsNullOrWhiteSpace($text)) {
    if ($text.StartsWith('/runs/')) {
      return Join-Path $RunsRootPath $text.Substring('/runs/'.Length)
    }
    if ($text -eq '/runs') {
      return $RunsRootPath
    }
  }
  return Join-Path $RunsRootPath $RunId
}

function Test-HealthFields($Health) {
  $required = @('healthy','repo_ok','skill_ok','ollama_ok','model_visible','router_ok')
  $failed = @()
  foreach ($field in $required) {
    if (-not ($Health.PSObject.Properties.Name -contains $field) -or $Health.$field -ne $true) {
      $failed += $field
    }
  }
  return $failed
}

$SourceRootPath = Resolve-AbsolutePath $SourceRoot (Get-Location).Path
$RunsRootPath = if ([string]::IsNullOrWhiteSpace($RunsRoot)) {
  Join-Path $SourceRootPath 'agent-test-runs'
} else {
  $RunsRoot
}
New-Item -ItemType Directory -Force -Path $RunsRootPath | Out-Null
$RunsRootPath = (Resolve-Path -LiteralPath $RunsRootPath).Path

$RuntimeScriptPath = Resolve-AbsolutePath $RuntimeScript (Join-Path $SourceRootPath 'agent-test-runtime\run_task.sh')
$RunSetId = 'container-live-chain-' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')
$EvidenceDir = Join-Path $RunsRootPath $RunSetId
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$script:Steps = @()
$ApiBase = "http://127.0.0.1:$ApiHostPort"

$summary = [ordered]@{
  schema_version = 'container-live-chain-test.v1'
  run_set_id = $RunSetId
  started_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  source_root = $SourceRootPath
  runs_root = $RunsRootPath
  evidence_dir = $EvidenceDir
  container_name = $ContainerName
  image = $Image
  api_base = $ApiBase
  ollama_base_url = $OllamaBaseUrl
  model_name = $ModelName
  runtime_override_id = $RuntimeOverrideId
  live_gate_mode = $LiveGateMode
  require_fab_policy_preflight = [bool]$RequireFabPolicyPreflight
  fab_agent_host_runtime_dir = ''
  fab_agent_container_runtime_dir = ''
  overall_status = 'failed'
  failure_category = ''
  steps = @()
}

function Invoke-LiveNonceGate([string]$GateName, [string]$TaskText, [int]$TimeoutSeconds) {
  $nonce = 'SDK_TEST_' + $GateName.ToUpper().Replace('-', '_') + '_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss')
  $task = $TaskText.Replace('__NONCE__', $nonce)
  $initial = Invoke-CurlJsonPost "$ApiBase/run-task" @{
    task = $task
    timeout_seconds = $TimeoutSeconds
  } $GateName
  $final = Wait-Run ([string]$initial.run_id) $GateName $TimeoutSeconds
  $runId = [string]$initial.run_id
  $text = "$($final.raw)`n$($final.parsed.result_text)"
  $hostRunDir = Convert-RunDirToHostPath $final.parsed.run_dir $runId
  $contractPath = Join-Path $hostRunDir 'task-contract.json'
  $contract = $null
  if (Test-Path -LiteralPath $contractPath) {
    $contract = Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
    Copy-Item -LiteralPath $contractPath -Destination (Join-Path $EvidenceDir "$GateName-task-contract.json") -Force
  }
  $gate = [ordered]@{
    gate = $GateName
    run_id = $runId
    run_dir = $hostRunDir
    status = [string]$final.parsed.status
    return_code = $final.parsed.return_code
    nonce = $nonce
    nonce_present = ($text -match [regex]::Escape($nonce))
    contract_path = $contractPath
    contract_present = ($null -ne $contract)
    contract_passed = ($null -ne $contract -and $contract.passed -eq $true)
    failure_category = ''
  }
  if ($gate.status -eq 'timeout') {
    $gate.failure_category = "CLAUDE_CODE_$($GateName.ToUpper().Replace('-', '_'))_TIMEOUT"
  } elseif ($gate.status -eq 'interrupted') {
    $gate.failure_category = "CLAUDE_CODE_$($GateName.ToUpper().Replace('-', '_'))_INTERRUPTED"
  } elseif ($gate.status -ne 'succeeded') {
    $gate.failure_category = if ($gate.contract_present -and -not $gate.contract_passed) { "CLAUDE_CODE_$($GateName.ToUpper().Replace('-', '_'))_TASK_CONTRACT_FAILED" } else { "CLAUDE_CODE_$($GateName.ToUpper().Replace('-', '_'))_FAILED" }
  } elseif ([int]$gate.return_code -ne 0) {
    $gate.failure_category = "CLAUDE_CODE_$($GateName.ToUpper().Replace('-', '_'))_NONZERO_EXIT"
  } elseif (-not $gate.contract_passed) {
    $gate.failure_category = "CLAUDE_CODE_$($GateName.ToUpper().Replace('-', '_'))_TASK_CONTRACT_FAILED"
  } elseif (-not $gate.nonce_present) {
    $gate.failure_category = "CLAUDE_CODE_$($GateName.ToUpper().Replace('-', '_'))_OUTPUT_MISSING"
  }
  Save-Json (Join-Path $EvidenceDir "$GateName-gate-result.json") $gate
  return $gate
}

function Invoke-ArtifactLiteGate([int]$TimeoutSeconds) {
  $nonce = 'ARTIFACT_OK_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss')
  $task = "Use bounded tool/file execution to create exactly one artifact file at ptt-stock-live/proof.txt containing exactly this text: $nonce. Then reply with exactly this nonce in the final answer: $nonce"
  $initial = Invoke-CurlJsonPost "$ApiBase/run-task" @{
    task = $task
    timeout_seconds = $TimeoutSeconds
  } 'artifact-lite'
  $final = Wait-Run ([string]$initial.run_id) 'artifact-lite' $TimeoutSeconds
  $runId = [string]$initial.run_id
  $text = "$($final.raw)`n$($final.parsed.result_text)"
  $hostRunDir = Convert-RunDirToHostPath $final.parsed.run_dir $runId
  $contractPath = Join-Path $hostRunDir 'task-contract.json'
  $contract = $null
  if (Test-Path -LiteralPath $contractPath) {
    $contract = Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
    Copy-Item -LiteralPath $contractPath -Destination (Join-Path $EvidenceDir 'artifact-lite-task-contract.json') -Force
  }
  $candidatePaths = @(
    (Join-Path $hostRunDir 'ptt-stock-live\proof.txt'),
    (Join-Path $hostRunDir 'worktree\proof.txt'),
    (Join-Path $hostRunDir 'proof.txt')
  )
  $artifactPath = ''
  $artifactText = ''
  foreach ($candidate in $candidatePaths) {
    if (Test-Path -LiteralPath $candidate) {
      $artifactPath = $candidate
      $artifactText = Get-Content -LiteralPath $candidate -Raw
      Copy-Item -LiteralPath $candidate -Destination (Join-Path $EvidenceDir 'artifact-lite-proof.txt') -Force
      break
    }
  }
  $gate = [ordered]@{
    gate = 'artifact-lite'
    run_id = $runId
    run_dir = $hostRunDir
    status = [string]$final.parsed.status
    return_code = $final.parsed.return_code
    nonce = $nonce
    nonce_present = ($text -match [regex]::Escape($nonce))
    contract_path = $contractPath
    contract_present = ($null -ne $contract)
    contract_passed = ($null -ne $contract -and $contract.passed -eq $true)
    artifact_path = $artifactPath
    artifact_present = (-not [string]::IsNullOrWhiteSpace($artifactPath))
    artifact_contains_nonce = ($artifactText -match [regex]::Escape($nonce))
    failure_category = ''
  }
  if ($gate.status -eq 'timeout') {
    $gate.failure_category = 'ARTIFACT_LITE_TIMEOUT'
  } elseif ($gate.status -ne 'succeeded') {
    $gate.failure_category = if ($gate.contract_present -and -not $gate.contract_passed) { 'ARTIFACT_LITE_TASK_CONTRACT_FAILED' } else { 'ARTIFACT_LITE_FAILED' }
  } elseif ([int]$gate.return_code -ne 0) {
    $gate.failure_category = 'ARTIFACT_LITE_NONZERO_EXIT'
  } elseif (-not $gate.contract_passed) {
    $gate.failure_category = 'ARTIFACT_LITE_TASK_CONTRACT_FAILED'
  } elseif (-not $gate.artifact_present) {
    $gate.failure_category = 'ARTIFACT_LITE_FILE_MISSING'
  } elseif (-not $gate.artifact_contains_nonce) {
    $gate.failure_category = 'ARTIFACT_LITE_FILE_CONTENT_MISMATCH'
  } elseif (-not $gate.nonce_present) {
    $gate.failure_category = 'ARTIFACT_LITE_OUTPUT_MISSING'
  }
  Save-Json (Join-Path $EvidenceDir 'artifact-lite-gate-result.json') $gate
  return $gate
}

function Invoke-SiteLiteGate([int]$TimeoutSeconds) {
  $nonce = 'SITE_OK_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss')
  $task = @"
Shopping site lite gate.
Use shell or Python file-writing tools to create a dependency-free static shopping website output package under worktree/shopping-site.
Required files:
- worktree/shopping-site/index.html
- worktree/shopping-site/styles.css
- worktree/shopping-site/app.js
- worktree/shopping-site/README.md
Functional requirements:
- at least four products
- product grid
- add-to-cart buttons
- cart count update
- cart total update
- checkout stub that clearly says no real payment is processed
- README explains how to review the generated output
Reply with exactly this nonce in the final answer: $nonce
"@
  $initial = Invoke-CurlJsonPost "$ApiBase/run-task" @{
    task = $task
    timeout_seconds = $TimeoutSeconds
  } 'site-lite'
  $final = Wait-Run ([string]$initial.run_id) 'site-lite' $TimeoutSeconds
  $runId = [string]$initial.run_id
  $text = "$($final.raw)`n$($final.parsed.result_text)"
  $hostRunDir = Convert-RunDirToHostPath $final.parsed.run_dir $runId
  $contractPath = Join-Path $hostRunDir 'task-contract.json'
  $contract = $null
  if (Test-Path -LiteralPath $contractPath) {
    $contract = Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
    Copy-Item -LiteralPath $contractPath -Destination (Join-Path $EvidenceDir 'site-lite-task-contract.json') -Force
  }
  $verifierPath = Join-Path $EvidenceDir 'site-lite-verifier.json'
  $verifierRaw = & uv run python (Join-Path $SourceRootPath 'scripts\verify_generated_output_package.py') `
    (Join-Path $hostRunDir 'worktree') `
    --profile shopping-site `
    --json 2>&1
  $verifierExit = $LASTEXITCODE
  Save-Text $verifierPath ([string]($verifierRaw -join "`n"))
  $verifier = $null
  if ($verifierExit -eq 0 -and ([string]($verifierRaw -join "`n")) -match '^\s*\{') {
    $verifier = ([string]($verifierRaw -join "`n")) | ConvertFrom-Json
  }
  $gate = [ordered]@{
    gate = 'site-lite'
    run_id = $runId
    run_dir = $hostRunDir
    status = [string]$final.parsed.status
    return_code = $final.parsed.return_code
    nonce = $nonce
    nonce_present = ($text -match [regex]::Escape($nonce))
    contract_path = $contractPath
    contract_present = ($null -ne $contract)
    contract_passed = ($null -ne $contract -and $contract.passed -eq $true)
    verifier_path = $verifierPath
    verifier_exit_code = $verifierExit
    verifier_passed = ($null -ne $verifier -and $verifier.all_passed -eq $true)
    failure_category = ''
  }
  if ($gate.status -eq 'timeout') {
    $gate.failure_category = 'SITE_LITE_TIMEOUT'
  } elseif ($gate.status -ne 'succeeded') {
    $gate.failure_category = if ($gate.contract_present -and -not $gate.contract_passed) { 'SITE_LITE_TASK_CONTRACT_FAILED' } else { 'SITE_LITE_FAILED' }
  } elseif ([int]$gate.return_code -ne 0) {
    $gate.failure_category = 'SITE_LITE_NONZERO_EXIT'
  } elseif (-not $gate.contract_passed) {
    $gate.failure_category = 'SITE_LITE_TASK_CONTRACT_FAILED'
  } elseif (-not $gate.nonce_present) {
    $gate.failure_category = 'SITE_LITE_OUTPUT_MISSING'
  } elseif (-not $gate.verifier_passed) {
    $gate.failure_category = 'SITE_LITE_VERIFIER_FAILED'
  }
  Save-Json (Join-Path $EvidenceDir 'site-lite-gate-result.json') $gate
  return $gate
}

function Convert-HostRunPathToContainerPath([string]$HostPath) {
  $resolved = (Resolve-Path -LiteralPath $HostPath).Path
  $root = $RunsRootPath.TrimEnd('\')
  if ($resolved -eq $root) {
    return '/runs'
  }
  if (-not $resolved.StartsWith($root + '\')) {
    throw "Fab policy runtime dir must be under runs root so it is mounted into the container. path=$resolved runs_root=$RunsRootPath"
  }
  $relative = $resolved.Substring($root.Length + 1).Replace('\','/')
  return "/runs/$relative"
}

function Prepare-FabPolicyRuntimeDir {
  if (-not [string]::IsNullOrWhiteSpace($FabAgentHostRuntimeDir)) {
    return (Resolve-Path -LiteralPath $FabAgentHostRuntimeDir).Path
  }
  $policyRoot = Join-Path $EvidenceDir 'fab-policy'
  New-Item -ItemType Directory -Force -Path $policyRoot | Out-Null
  $resolveOutput = & uv run python (Join-Path $SourceRootPath 'scripts\resolve_fab_agent.py') `
    (Join-Path $SourceRootPath 'fab_agents\examples\fab_frontend_builder') `
    --out $policyRoot 2>&1
  $exit = $LASTEXITCODE
  Save-Text (Join-Path $EvidenceDir 'fab-policy-resolve.stdout.txt') ([string]($resolveOutput -join "`n"))
  if ($exit -ne 0) {
    throw "resolve_fab_agent failed for container Fab policy preflight exit=$exit output=$resolveOutput"
  }
  $expected = Join-Path $policyRoot 'fab_frontend_builder'
  if (-not (Test-Path -LiteralPath (Join-Path $expected 'effective-agent.json'))) {
    throw "resolved Fab policy missing effective-agent.json: $expected"
  }
  return (Resolve-Path -LiteralPath $expected).Path
}

try {
  if ($RequireFabPolicyPreflight) {
    $fabHostDir = Prepare-FabPolicyRuntimeDir
    $fabContainerDir = Convert-HostRunPathToContainerPath $fabHostDir
    $summary.fab_agent_host_runtime_dir = $fabHostDir
    $summary.fab_agent_container_runtime_dir = $fabContainerDir
    Add-Step 'fab-policy-preflight-setup' 'pass' 'Fab policy runtime dir prepared' @{
      host_runtime_dir = $fabHostDir
      container_runtime_dir = $fabContainerDir
    }
  }

  if (-not $SkipContainerStart) {
    Add-Step 'container-start' 'running' "starting $ContainerName"
    $oldPreference = $ErrorActionPreference
    try {
      $ErrorActionPreference = 'Continue'
      docker rm -f $ContainerName 2>$null | Out-Null
    } finally {
      $ErrorActionPreference = $oldPreference
    }
    $dockerArgs = @(
      'run','-d',
      '--name', $ContainerName,
      '-p', "$ApiHostPort`:8080",
      '-e', "OLLAMA_BASE_URL=$OllamaBaseUrl",
      '-e', "MODEL_NAME=$ModelName",
      '-e', 'START_CONTAINER_OLLAMA=false',
      '-e', 'TASK_EXECUTOR=claude-code',
      '-e', 'REQUIRE_REPO_RUNTIME_OVERRIDE=true',
      '-e', "RUNTIME_OVERRIDE_ID=$RuntimeOverrideId",
      '-e', 'RUN_REPO_SMOKE_ON_TASK=false',
      '-e', 'MULTI_AGENT_REPO=/workspace/multi_agent_claude_code',
      '-e', 'RUNS_DIR=/runs',
      '-e', 'API_KEY=local-router-token',
      '-e', 'ANTHROPIC_AUTH_TOKEN=local-router-token',
      '-e', 'ANTHROPIC_BASE_URL=http://127.0.0.1:3456',
      '-v', "$SourceRootPath`:/workspace/multi_agent_claude_code",
      '-v', "$RunsRootPath`:/runs",
      '-v', "$RuntimeScriptPath`:/app/runtime/run_task.sh:ro",
      $Image
    )
    if ($RequireFabPolicyPreflight) {
      $dockerArgs = @(
        $dockerArgs[0..($dockerArgs.Length - 2)] +
        @(
          '-e', 'REQUIRE_FAB_EFFECTIVE_POLICY=true',
          '-e', "FAB_AGENT_RUNTIME_DIR=$($summary.fab_agent_container_runtime_dir)"
        ) +
        $dockerArgs[-1]
      )
    }
    Save-Json (Join-Path $EvidenceDir 'docker-run-args.json') $dockerArgs
    $containerId = docker @dockerArgs 2>&1
    $dockerExit = $LASTEXITCODE
    Save-Text (Join-Path $EvidenceDir 'docker-run.stdout.txt') ([string]$containerId)
    if ($dockerExit -ne 0) {
      throw "docker run failed exit=$dockerExit body=$containerId"
    }
    Add-Step 'container-start' 'pass' "started $ContainerName" @{ container_id = [string]$containerId }
  } else {
    Add-Step 'container-start' 'skipped' 'SkipContainerStart was set'
  }

  $health = $null
  $healthFailed = @('not_checked')
  for ($i = 1; $i -le 24; $i++) {
    try {
      $health = Invoke-CurlJsonGet "$ApiBase/health" (Join-Path $EvidenceDir 'health.json') 15
      $healthFailed = Test-HealthFields $health
      if ($healthFailed.Count -eq 0) { break }
    } catch {
      Save-Text (Join-Path $EvidenceDir 'health-error.txt') ([string]$_)
    }
    Start-Sleep -Seconds 5
  }
  if ($healthFailed.Count -ne 0) {
    $summary.failure_category = 'HEALTH_FAILED'
    Add-Step 'health' 'fail' "health required fields failed: $($healthFailed -join ',')"
    throw $summary.failure_category
  }
  Add-Step 'health' 'pass' 'health required fields passed'

  $markerInitial = Invoke-CurlJsonPost "$ApiBase/run-task" @{
    task = 'Runtime override marker check. Print the mounted repository runtime marker and do not run a real task.'
    timeout_seconds = $MarkerTimeoutSeconds
  } 'marker'
  $markerFinal = Wait-Run ([string]$markerInitial.run_id) 'marker' $MarkerTimeoutSeconds
  $markerText = "$($markerFinal.raw)`n$($markerFinal.parsed.result_text)"
  if ([string]$markerFinal.parsed.status -ne 'succeeded' -or $markerText -notmatch [regex]::Escape("RUNTIME_OVERRIDE_MARKER:$RuntimeOverrideId")) {
    $summary.failure_category = 'RUNTIME_OVERRIDE_NOT_ACTIVE'
    Add-Step 'runtime-marker' 'fail' "marker not found for run_id=$($markerInitial.run_id)"
    throw $summary.failure_category
  }
  Add-Step 'runtime-marker' 'pass' "marker verified run_id=$($markerInitial.run_id)" @{ run_id = $markerInitial.run_id }

  $liveGates = @()
  if ($LiveGateMode -in @('minimal','all')) {
    $minimalGate = Invoke-LiveNonceGate 'minimal-nonce' 'Reply with exactly this text and nothing else: __NONCE__' $LiveTimeoutSeconds
    $liveGates += $minimalGate
    if (-not [string]::IsNullOrWhiteSpace($minimalGate.failure_category)) {
      $summary.failure_category = $minimalGate.failure_category
      Add-Step 'minimal-nonce' 'fail' "minimal nonce failed run_id=$($minimalGate.run_id)" $minimalGate
      throw $summary.failure_category
    }
    Add-Step 'minimal-nonce' 'pass' "minimal nonce verified run_id=$($minimalGate.run_id)" $minimalGate
  }
  if ($LiveGateMode -in @('skill-visible','all')) {
    $skillVisibleGate = Invoke-LiveNonceGate 'skill-visible-nonce' 'Without reading files or running tools, state whether the research-task-orchestrator skill name is available in the current Claude Code environment, then end with exactly this nonce: __NONCE__' $LiveTimeoutSeconds
    $liveGates += $skillVisibleGate
    if (-not [string]::IsNullOrWhiteSpace($skillVisibleGate.failure_category)) {
      $summary.failure_category = $skillVisibleGate.failure_category
      Add-Step 'skill-visible-nonce' 'fail' "skill-visible nonce failed run_id=$($skillVisibleGate.run_id)" $skillVisibleGate
      throw $summary.failure_category
    }
    Add-Step 'skill-visible-nonce' 'pass' "skill-visible nonce verified run_id=$($skillVisibleGate.run_id)" $skillVisibleGate
  }
  if ($LiveGateMode -in @('skill-lite','all')) {
    $skillLiteGate = Invoke-LiveNonceGate 'skill-lite-nonce' 'Use the research-task-orchestrator skill only as high-level instruction context. Do not run tools, do not inspect files, do not start subagents, and do not create artifacts. Reply with exactly this nonce and nothing else: __NONCE__' $LiveTimeoutSeconds
    $liveGates += $skillLiteGate
    if (-not [string]::IsNullOrWhiteSpace($skillLiteGate.failure_category)) {
      $summary.failure_category = $skillLiteGate.failure_category
      Add-Step 'skill-lite-nonce' 'fail' "skill-lite nonce failed run_id=$($skillLiteGate.run_id)" $skillLiteGate
      throw $summary.failure_category
    }
    Add-Step 'skill-lite-nonce' 'pass' "skill-lite nonce verified run_id=$($skillLiteGate.run_id)" $skillLiteGate
  }
  if ($LiveGateMode -in @('skill','all')) {
    $skillGate = Invoke-LiveNonceGate 'skill-nonce' 'Use the research-task-orchestrator skill only as high-level instruction context. Do not run tools, do not inspect files, do not start subagents, and do not create artifacts. Reply with exactly this nonce and nothing else: __NONCE__' $LiveTimeoutSeconds
    $liveGates += $skillGate
    if (-not [string]::IsNullOrWhiteSpace($skillGate.failure_category)) {
      $summary.failure_category = $skillGate.failure_category
      Add-Step 'skill-nonce' 'fail' "skill nonce failed run_id=$($skillGate.run_id)" $skillGate
      throw $summary.failure_category
    }
    Add-Step 'skill-nonce' 'pass' "skill nonce verified run_id=$($skillGate.run_id)" $skillGate
  }
  if ($LiveGateMode -in @('artifact-lite','all')) {
    $artifactGate = Invoke-ArtifactLiteGate $LiveTimeoutSeconds
    $liveGates += $artifactGate
    if (-not [string]::IsNullOrWhiteSpace($artifactGate.failure_category)) {
      $summary.failure_category = $artifactGate.failure_category
      Add-Step 'artifact-lite' 'fail' "artifact-lite failed run_id=$($artifactGate.run_id)" $artifactGate
      throw $summary.failure_category
    }
    Add-Step 'artifact-lite' 'pass' "artifact-lite verified run_id=$($artifactGate.run_id)" $artifactGate
  }
  if ($LiveGateMode -in @('site-lite','all')) {
    $siteGate = Invoke-SiteLiteGate $LiveTimeoutSeconds
    $liveGates += $siteGate
    if (-not [string]::IsNullOrWhiteSpace($siteGate.failure_category)) {
      $summary.failure_category = $siteGate.failure_category
      Add-Step 'site-lite' 'fail' "site-lite failed run_id=$($siteGate.run_id)" $siteGate
      throw $summary.failure_category
    }
    Add-Step 'site-lite' 'pass' "site-lite verified run_id=$($siteGate.run_id)" $siteGate
  }
  if ($LiveGateMode -eq 'skill-heavy') {
    $skillHeavyGate = Invoke-LiveNonceGate 'skill-heavy-nonce' 'Use the mounted research-task-orchestrator skill context if available, but do not inspect files. Reply with exactly this nonce in the final answer: __NONCE__' $LiveTimeoutSeconds
    $liveGates += $skillHeavyGate
    if (-not [string]::IsNullOrWhiteSpace($skillHeavyGate.failure_category)) {
      $summary.failure_category = $skillHeavyGate.failure_category
      Add-Step 'skill-heavy-nonce' 'fail' "skill-heavy nonce failed run_id=$($skillHeavyGate.run_id)" $skillHeavyGate
      throw $summary.failure_category
    }
    Add-Step 'skill-heavy-nonce' 'pass' "skill-heavy nonce verified run_id=$($skillHeavyGate.run_id)" $skillHeavyGate
  }

  $summary.overall_status = 'pass'
  $summary.live_gates = $liveGates
} catch {
  if ([string]::IsNullOrWhiteSpace($summary.failure_category)) {
    $errorText = [string]$_
    if ($errorText -match 'curl: \(7\)|Could not connect|Failed to connect') {
      $summary.failure_category = 'API_UNAVAILABLE_DURING_TEST'
    } else {
      $summary.failure_category = 'UNCLASSIFIED_CONTAINER_LIVE_CHAIN_FAILURE'
    }
  }
  $summary.error = [string]$_
  if ($summary.overall_status -ne 'pass') {
    $summary.overall_status = 'failed'
  }
} finally {
  $summary.finished_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  $summary.steps = $script:Steps
  Save-Json (Join-Path $EvidenceDir 'container-live-chain-summary.json') $summary
  if (-not $KeepContainer -and -not $SkipContainerStart) {
    docker rm -f $ContainerName 2>$null | Out-Null
  }
}

$summary | ConvertTo-Json -Depth 50
if ($summary.overall_status -ne 'pass') {
  exit 1
}
