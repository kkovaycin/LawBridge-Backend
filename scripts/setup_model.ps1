param(
    [Parameter(Mandatory = $true)]
    [string]$ZipPath,
    [string]$DestinationRoot
)

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $DestinationRoot) {
    $DestinationRoot = Join-Path $scriptDirectory "..\\models"
}

$resolvedZipPath = (Resolve-Path -LiteralPath $ZipPath).Path
$resolvedDestinationRoot = [System.IO.Path]::GetFullPath($DestinationRoot)

if (-not (Test-Path -LiteralPath $resolvedZipPath)) {
    throw "Zip file not found: $ZipPath"
}

New-Item -ItemType Directory -Force -Path $resolvedDestinationRoot | Out-Null
Expand-Archive -LiteralPath $resolvedZipPath -DestinationPath $resolvedDestinationRoot -Force

$modelDirectory = Get-ChildItem -LiteralPath $resolvedDestinationRoot -Directory | Select-Object -First 1

if (-not $modelDirectory) {
    throw "No model directory was extracted into $resolvedDestinationRoot"
}

Write-Output "Model extracted to: $($modelDirectory.FullName)"
