$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:CLOUDSDK_CONFIG = Join-Path $repoRoot ".gcloud"
$gcloud = Join-Path $env:LOCALAPPDATA "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

if (-not (Test-Path $gcloud)) {
  throw "Google Cloud CLI was not found at: $gcloud"
}

New-Item -ItemType Directory -Force -Path $env:CLOUDSDK_CONFIG | Out-Null

Write-Host "Using CLOUDSDK_CONFIG=$env:CLOUDSDK_CONFIG"
Write-Host "A browser login may open. If it does not, copy the URL shown by gcloud."
& $gcloud auth login
& $gcloud auth list

