$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$runtimeRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
$pythonExe = Join-Path $runtimeRoot 'python\python.exe'
$nodeExe = Join-Path $runtimeRoot 'node\bin\node.exe'
$sharedModules = Join-Path $runtimeRoot 'node\node_modules'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Bundled Python missing. See README for a standard Python run.' }
& $pythonExe run_project.py
if ($LASTEXITCODE -ne 0) { throw 'Analysis failed. See outputs/demo/test_results.txt.' }
if (-not (Test-Path -LiteralPath $nodeExe)) { throw 'Analysis updated, but Excel export needs the bundled Node runtime. Existing Excel is stale.' }
if (-not (Test-Path -LiteralPath (Join-Path $sharedModules '@oai\artifact-tool'))) { throw 'Excel export dependency is missing. Existing Excel is stale.' }
$moduleLink = Join-Path $PSScriptRoot 'tools\node_modules'
if (-not (Test-Path -LiteralPath $moduleLink)) {
    New-Item -ItemType Junction -Path $moduleLink -Target $sharedModules | Out-Null
}
& $nodeExe tools/export_workbook.mjs
if ($LASTEXITCODE -ne 0) { throw 'Excel export failed. Analysis and CSV remain available.' }
& $pythonExe tools/verify_outputs.py
if ($LASTEXITCODE -ne 0) { throw 'Output consistency checks failed.' }
Write-Output 'Done. Open outputs/demo/index.html. Raw source files are preserved.'
