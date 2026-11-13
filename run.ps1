param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GroupArguments)
$ErrorActionPreference = 'Stop'
$taskCandidates = @()
if ($env:GROUPCTL_PYTHON) {
    $taskCandidates += @{Path=$env:GROUPCTL_PYTHON; Prefix=@()}
} else {
    foreach ($taskName in @('python.exe','python3.exe','py.exe')) {
        $taskInstalled = Get-Command $taskName -ErrorAction SilentlyContinue
        if ($taskInstalled -and $taskInstalled.Source -notlike '*Microsoft\WindowsApps\python*') {
            $taskPrefix = @()
            if ($taskName -eq 'py.exe') { $taskPrefix = @('-3') }
            $taskCandidates += @{Path=$taskInstalled.Source; Prefix=$taskPrefix}
        }
    }
    $taskBundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $taskBundled) { $taskCandidates += @{Path=$taskBundled; Prefix=@()} }
}
$taskPython = $null
foreach ($taskCandidate in $taskCandidates) {
    try {
        $taskPrefix = $taskCandidate.Prefix
        & $taskCandidate.Path @taskPrefix -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $taskPython=$taskCandidate; break }
    } catch { continue }
}
if (-not $taskPython) { throw 'Python 3.10+ is required. Install Python or set GROUPCTL_PYTHON to python.exe.' }
$taskOldPath = $env:PYTHONPATH
$taskOldEncoding = $env:PYTHONIOENCODING
$env:PYTHONPATH = $PSScriptRoot + [IO.Path]::PathSeparator + $taskOldPath
$env:PYTHONIOENCODING = 'utf-8'
$taskPrefix = $taskPython.Prefix
try {
    if ($GroupArguments.Count -gt 0 -and $GroupArguments[0] -eq 'demo') {
        $taskRest = @($GroupArguments | Select-Object -Skip 1)
        & $taskPython.Path @taskPrefix (Join-Path $PSScriptRoot 'scripts\demo.py') @taskRest
    } elseif ($GroupArguments.Count -gt 0 -and $GroupArguments[0] -eq 'test-suite') {
        Push-Location $PSScriptRoot
        try { & $taskPython.Path @taskPrefix -m unittest discover -s tests -v } finally { Pop-Location }
    } else {
        & $taskPython.Path @taskPrefix -m groupctl @GroupArguments
    }
    $taskExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $taskOldPath
    $env:PYTHONIOENCODING = $taskOldEncoding
}
exit $taskExitCode
