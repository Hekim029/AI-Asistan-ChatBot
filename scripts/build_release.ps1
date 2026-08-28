$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot "venv\Scripts\python.exe"
$spec = Join-Path $projectRoot "HekoAI.spec"
$exe = Join-Path $projectRoot "dist\HekoAI.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Sanal ortam bulunamadı: $python"
}

Push-Location $projectRoot
try {
    & $python -m compileall -q main.py ui core services memory utils evals tests
    if ($LASTEXITCODE -ne 0) { throw "Sözdizimi kontrolü başarısız." }

    & $python -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw "Birim testleri başarısız." }

    & $python -m evals.run_evals
    if ($LASTEXITCODE -ne 0) { throw "Çevrimdışı kalite değerlendirmesi başarısız." }

    & $python -X utf8 -m bandit -q -ll -r core services memory ui utils main.py -x tests
    if ($LASTEXITCODE -ne 0) { throw "Orta/yüksek güvenlik taraması başarısız." }

    & $python -m PyInstaller --noconfirm --clean $spec
    if ($LASTEXITCODE -ne 0) { throw "EXE paketleme başarısız." }
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "Paketleme tamamlandı ancak HekoAI.exe bulunamadı."
    }

    $item = Get-Item -LiteralPath $exe
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $exe
    Write-Host ""
    Write-Host "Yayın paketi hazır"
    Write-Host "Dosya : $($item.FullName)"
    Write-Host "Boyut : $([math]::Round($item.Length / 1MB, 1)) MB"
    Write-Host "SHA256: $($hash.Hash)"
}
finally {
    Pop-Location
}
