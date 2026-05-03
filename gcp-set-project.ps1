param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectId,

  [string]$Zone
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:CLOUDSDK_CONFIG = Join-Path $repoRoot ".gcloud"
$gcloud = Join-Path $env:LOCALAPPDATA "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

if (-not (Test-Path $gcloud)) {
  throw "Google Cloud CLI was not found at: $gcloud"
}

New-Item -ItemType Directory -Force -Path $env:CLOUDSDK_CONFIG | Out-Null

& $gcloud config set project $ProjectId

if ($Zone) {
  & $gcloud config set compute/zone $Zone
}

& $gcloud config list

