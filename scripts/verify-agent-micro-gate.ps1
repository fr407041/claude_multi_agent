param(
  [Parameter(Mandatory = $true)][ValidateSet('A','B','C','D','E','F')][string]$Gate,
  [Parameter(Mandatory = $true)][string]$RunDir
)

$ErrorActionPreference = 'Stop'

function New-Result($Pass, $Reasons, $Details) {
  [ordered]@{
    pass = [bool]$Pass
    gate = $Gate
    run_dir = $RunDir
    checked_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    fail_reasons = @($Reasons)
    details = $Details
  }
}

function Read-JsonFile($Path) {
  if (-not (Test-Path $Path)) {
    throw "missing file: $Path"
  }
  Get-Content $Path -Raw | ConvertFrom-Json
}

function To-Array($Value) {
  if ($null -eq $Value) { return @() }
  if ($Value -is [System.Array]) { return @($Value) }
  return @($Value)
}

function Get-UrlList($Json) {
  if ($Json -is [System.Array]) { return @($Json) }
  if ($Json.urls) { return @(To-Array $Json.urls) }
  if ($Json.articles) {
    return @(To-Array $Json.articles | ForEach-Object {
      if ($_ -is [string]) { $_ } else { $_.url }
    })
  }
  return @()
}

$artifactDir = Join-Path $RunDir 'ptt-stock-live'
$reasons = New-Object System.Collections.Generic.List[string]
$details = [ordered]@{
  artifact_dir = $artifactDir
  artifact_dir_exists = (Test-Path $artifactDir)
}

if (-not (Test-Path $RunDir)) {
  $reasons.Add("run dir missing")
  New-Result $false $reasons $details | ConvertTo-Json -Depth 20
  exit 1
}

if (-not (Test-Path $artifactDir)) {
  $reasons.Add("ptt-stock-live artifact dir missing")
}

try {
  switch ($Gate) {
    'A' {
      $proof = Join-Path $artifactDir 'proof.txt'
      $details.proof_path = $proof
      if (-not (Test-Path $proof)) {
        $reasons.Add("proof.txt missing")
      } else {
        $content = (Get-Content $proof -Raw).Trim()
        $details.proof_content = $content
        if ($content -ne 'TOOL_EXECUTED_OK') {
          $reasons.Add("proof.txt content mismatch")
        }
      }
    }
    'B' {
      $index = Join-Path $artifactDir 'index.html'
      $details.index_path = $index
      if (-not (Test-Path $index)) {
        $reasons.Add("index.html missing")
      } else {
        $html = Get-Content $index -Raw
        $bytes = (Get-Item $index).Length
        $containsMarker = ($html -match '/bbs/Stock/' -or $html -match 'r-ent' -or $html -match 'Stock')
        $details.bytes = $bytes
        $details.contains_stock_board_marker = $containsMarker
        if ($bytes -lt 500) { $reasons.Add("index.html too small") }
        if (-not $containsMarker) { $reasons.Add("index.html lacks PTT Stock markers") }
      }
    }
    'C' {
      $urlsFile = Join-Path $artifactDir 'urls.json'
      $details.urls_path = $urlsFile
      try {
        $json = Read-JsonFile $urlsFile
        $urls = @(Get-UrlList $json | Where-Object { $_ })
        $unique = @($urls | Select-Object -Unique)
        $valid = @($unique | Where-Object { $_ -match '^https://www\.ptt\.cc/bbs/Stock/.+\.html$' })
        $details.url_count = $urls.Count
        $details.unique_url_count = $unique.Count
        $details.valid_ptt_stock_url_count = $valid.Count
        if ($unique.Count -ne 5) { $reasons.Add("expected exactly 5 unique URLs") }
        if ($valid.Count -ne 5) { $reasons.Add("not all URLs are valid PTT Stock article URLs") }
      } catch {
        $reasons.Add("urls.json parse/check failed: $($_.Exception.Message)")
      }
    }
    'D' {
      $articleFile = Join-Path $artifactDir 'article.json'
      $details.article_path = $articleFile
      try {
        $article = Read-JsonFile $articleFile
        $title = [string]$article.title
        $url = [string]$article.url
        $body = [string]$article.body
        $details.title_length = $title.Length
        $details.body_length = $body.Length
        $details.url = $url
        if ([string]::IsNullOrWhiteSpace($title)) { $reasons.Add("article title missing") }
        if ($url -notmatch '^https://www\.ptt\.cc/bbs/Stock/.+\.html$') { $reasons.Add("article URL invalid") }
        if ([string]::IsNullOrWhiteSpace($body) -or $body.Length -lt 100) { $reasons.Add("article body missing or too short") }
      } catch {
        $reasons.Add("article.json parse/check failed: $($_.Exception.Message)")
      }
    }
    { $_ -in @('E','F') } {
      $expectedCount = if ($Gate -eq 'E') { 3 } else { 20 }
      $finalFile = Join-Path $artifactDir 'final.json'
      $details.final_path = $finalFile
      $details.expected_article_count = $expectedCount
      try {
        $final = Read-JsonFile $finalFile
        $articles = @(To-Array $final.articles)
        $stocks = @(To-Array $final.stocks)
        $urls = @($articles | ForEach-Object { $_.url } | Where-Object { $_ })
        $uniqueUrls = @($urls | Select-Object -Unique)
        $validUrls = @($uniqueUrls | Where-Object { $_ -match '^https://www\.ptt\.cc/bbs/Stock/.+\.html$' })
        $details.article_count_field = $final.article_count
        $details.article_array_count = $articles.Count
        $details.unique_url_count = $uniqueUrls.Count
        $details.valid_url_count = $validUrls.Count
        $details.stock_count = $stocks.Count
        if ([int]$final.article_count -ne $expectedCount) { $reasons.Add("article_count field is not $expectedCount") }
        if ($articles.Count -ne $expectedCount) { $reasons.Add("articles array count is not $expectedCount") }
        if ($uniqueUrls.Count -ne $expectedCount) { $reasons.Add("article URLs are not exactly $expectedCount unique URLs") }
        if ($validUrls.Count -ne $expectedCount) { $reasons.Add("not all article URLs are valid PTT Stock URLs") }
        if ($stocks.Count -lt 1) { $reasons.Add("stocks array is empty") }
        $validStances = @('bullish','bearish','mixed','neutral','insufficient_evidence')
        $validConfidence = @('low','medium','high')
        foreach ($stock in $stocks) {
          $name = [string]$stock.ticker_or_name
          if ([string]::IsNullOrWhiteSpace($name)) { $reasons.Add("stock ticker_or_name missing") }
          if ($validStances -notcontains ([string]$stock.stance)) { $reasons.Add("invalid stance for stock: $name") }
          if ($validConfidence -notcontains ([string]$stock.confidence)) { $reasons.Add("invalid confidence for stock: $name") }
          foreach ($field in @('bullish_evidence','bearish_evidence','neutral_evidence','article_urls')) {
            if ($null -eq $stock.$field) { $reasons.Add("missing $field for stock: $name") }
          }
          $stockUrls = @(To-Array $stock.article_urls | Where-Object { $_ })
          if ($stockUrls.Count -lt 1) { $reasons.Add("empty article_urls for stock: $name") }
        }
      } catch {
        $reasons.Add("final.json parse/check failed: $($_.Exception.Message)")
      }
    }
  }
} catch {
  $reasons.Add("verifier crashed: $($_.Exception.Message)")
}

$pass = ($reasons.Count -eq 0)
New-Result $pass $reasons $details | ConvertTo-Json -Depth 20
if ($pass) { exit 0 } else { exit 1 }
