param(
  [string]$RemoteCommand
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:CLOUDSDK_CONFIG = Join-Path $repoRoot ".gcloud"
$gcloud = Join-Path $env:LOCALAPPDATA "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

if (-not (Test-Path $gcloud)) {
  throw "Google Cloud CLI was not found at: $gcloud"
}

New-Item -ItemType Directory -Force -Path $env:CLOUDSDK_CONFIG | Out-Null

$argsList = @(
  "compute",
  "ssh",
  "--zone",
  "us-west1-b",
  "instance-20260503-133643",
  "--project",
  "my-discord-bot-495213"
)

if ($RemoteCommand) {
  $argsList += @("--command", $RemoteCommand)
}

& $gcloud @argsList

