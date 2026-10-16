param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GroupArguments)
$ErrorActionPreference = 'Stop'
$taskPython = $null
$taskCandidates = @()
if ($env:GROUPCTL_PYTHON) { $taskCandidates += $env:GROUPCTL_PYTHON }
$taskBundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $taskBundledPython) { $taskCandidates += $taskBundledPython }
$taskInstalled = Get-Command python.exe -ErrorAction SilentlyContinue
if ($taskInstalled) { $taskCandidates += $taskInstalled.Source }
foreach ($taskCandidate in $taskCandidates) {
    & $taskCandidate -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>$null
    if ($LASTEXITCODE -eq 0) { $taskPython = $taskCandidate; break }
}
if (-not $taskPython) { throw 'Python 3.10+ is required. Set GROUPCTL_PYTHON to the python.exe path.' }
$taskOldPath = $env:PYTHONPATH
$env:PYTHONPATH = $PSScriptRoot + [IO.Path]::PathSeparator + $taskOldPath
$env:PYTHONIOENCODING = 'utf-8'
try {
    if ($GroupArguments.Count -gt 0 -and $GroupArguments[0] -eq 'demo') {
        $taskRest = @($GroupArguments | Select-Object -Skip 1)
        & $taskPython (Join-Path $PSScriptRoot 'scripts\demo.py') @taskRest
    } elseif ($GroupArguments.Count -gt 0 -and $GroupArguments[0] -eq 'test-suite') {
        Push-Location $PSScriptRoot
        try { & $taskPython -m unittest discover -s tests -v } finally { Pop-Location }
    } else {
        & $taskPython -m groupctl @GroupArguments
    }
    $taskExitCode = $LASTEXITCODE
} finally { $env:PYTHONPATH = $taskOldPath }
exit $taskExitCode
