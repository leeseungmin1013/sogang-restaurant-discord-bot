param(
  [Parameter(Mandatory = $true)]
  [string]$Instance,

  [string]$ProjectId,

  [string]$Zone,

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

$argsList = @("compute", "ssh", $Instance)

if ($ProjectId) {
  $argsList += @("--project", $ProjectId)
}

if ($Zone) {
  $argsList += @("--zone", $Zone)
}

if ($RemoteCommand) {
  $argsList += @("--command", $RemoteCommand)
}

& $gcloud @argsList

