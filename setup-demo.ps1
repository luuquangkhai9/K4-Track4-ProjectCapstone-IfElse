# Isolated Windows runtime with prebuilt conda-forge PyBullet; no system changes.
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.runtime'
$mamba = Join-Path $runtimeRoot 'Library/bin/micromamba.exe'
$pythonPrefix = Join-Path $runtimeRoot 'python'
New-Item -ItemType Directory -Force $runtimeRoot | Out-Null
if (-not (Test-Path -LiteralPath $mamba)) {
    $archivePath = Join-Path $runtimeRoot 'micromamba.tar.bz2'
    Invoke-WebRequest -Uri 'https://micro.mamba.pm/api/micromamba/win-64/latest' -OutFile $archivePath
    tar -xjf $archivePath -C $runtimeRoot Library/bin/micromamba.exe
    if ($LASTEXITCODE -ne 0) { throw 'Cannot extract micromamba' }
}
if (-not (Test-Path (Join-Path $pythonPrefix 'conda-meta/history'))) {
    & $mamba --root-prefix (Join-Path $runtimeRoot 'mamba') create --prefix $pythonPrefix --channel conda-forge python=3.11 pybullet=3.25 numpy=1.26 pip -y
    if ($LASTEXITCODE -ne 0) { throw 'Cannot prepare the simulation runtime' }
}
Push-Location $projectRoot
try {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv pip install --python (Join-Path $pythonPrefix 'python.exe') -r requirements-demo.txt -c requirements-vision-lock.txt
    } else {
        & (Join-Path $pythonPrefix 'python.exe') -m pip install -r requirements-demo.txt -c requirements-vision-lock.txt
    }
    if ($LASTEXITCODE -ne 0) { throw 'Cannot install vision dependencies' }
    & (Join-Path $pythonPrefix 'python.exe') -c "import numpy, pybullet, cv2, mediapipe; print('Runtime imports OK')"
    if ($LASTEXITCODE -ne 0) { throw 'Runtime import validation failed' }
    & (Join-Path $pythonPrefix 'python.exe') -m dev.download_model
    if ($LASTEXITCODE -ne 0) { throw 'Cannot download the hand model' }
} finally {
    Pop-Location
}
Write-Host 'Ready. Run: ./run-demo.ps1 --web'
