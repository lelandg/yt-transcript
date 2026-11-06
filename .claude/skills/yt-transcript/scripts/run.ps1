# PowerShell shim for the yt-transcript skill (Windows PowerShell, or pwsh on any OS).
# All logic lives in run.py; this only finds a Python and forwards the arguments.
# No $ErrorActionPreference = "Stop": under Windows PowerShell 5.1 that turns run.py's
# stderr progress lines into terminating errors when output is captured.
$py = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
if ($IsWindows -or $env:OS -eq "Windows_NT") { $py = "python" }
if (-not (Get-Command $py -ErrorAction SilentlyContinue)) {
    [Console]::Error.WriteLine("ERROR: Python interpreter '$py' not found on PATH.")
    exit 1
}
& $py (Join-Path $PSScriptRoot "run.py") @args
exit $LASTEXITCODE
