# PowerShell runner for the yt-transcript skill.
# Resolves the project root relative to this script's location, so the skill
# is portable — anyone who clones the repo gets a working setup.
#
# Venv lifecycle: prefer .venv_windows > .venv; create .venv_windows if neither
# exists; install requirements.txt if youtube_transcript_api isn't importable.
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# scripts\ -> yt-transcript\ -> skills\ -> .claude\ -> project root
$Project = (Resolve-Path (Join-Path $ScriptDir "..\..\..\..")).Path

Set-Location $Project

if (Test-Path ".venv_windows") {
    $Venv = ".venv_windows"
} elseif (Test-Path ".venv") {
    $Venv = ".venv"
} else {
    $Venv = ".venv_windows"
    Write-Host ">>> No venv found. Creating $Project\$Venv ..."
    python -m venv $Venv
}

& "$Project\$Venv\Scripts\Activate.ps1"

# Probe for the module; suppress stderr so a missing import isn't noisy.
python -c "import youtube_transcript_api" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host ">>> Installing requirements into $Venv ..."
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
}

# Default output dir is .\Notes (we're cwd'd into the project).
# User-supplied -d will override via argparse last-wins.
python yt_transcript.py @args
exit $LASTEXITCODE
