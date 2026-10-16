# Pass all arguments through to main.py in the project's isolated runtime.
$ErrorActionPreference = 'Stop'
$pythonPrefix = Join-Path $PSScriptRoot '.runtime/python'
if (-not (Test-Path (Join-Path $pythonPrefix 'python.exe'))) {
    throw 'Runtime missing. Run ./setup-demo.ps1 first.'
}
Push-Location $PSScriptRoot
try {
    & (Join-Path $pythonPrefix 'python.exe') main.py @args
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $result
