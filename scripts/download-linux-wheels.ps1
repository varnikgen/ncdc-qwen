# Run on a PC that CAN reach pypi.org (your Windows box).
# Produces Linux/CPython 3.11 wheels for the container image.
# Usage (from repo root):
#   .\scripts\download-linux-wheels.ps1
# Then copy vendor\py311-linux\ to the server and rebuild.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Dest = Join-Path $Root "vendor\py311-linux"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

python -m pip download `
  -r (Join-Path $Root "requirements.txt") `
  -d $Dest `
  --python-version 311 `
  --platform manylinux_2_17_x86_64 `
  --implementation cp `
  --abi cp311 `
  --only-binary=:all: `
  --trusted-host pypi.org `
  --trusted-host files.pythonhosted.org

Write-Host "Wheels saved to $Dest"
Get-ChildItem $Dest | Select-Object Name, Length
