# Sync E:\...\EdgeAI-ZU4EV_Claude -> Ubuntu-18.04 /home/atw/Edge_AI_Acc/...
$ErrorActionPreference = "Stop"
$RepoWin = "E:\WSL_ENV\project\EdgeAI-ZU4EV_Claude"
if (-not (Test-Path $RepoWin)) {
    Write-Error "Windows repo not found: $RepoWin"
}
Write-Host "[sync] Ubuntu-18.04 / atw <- $RepoWin"
wsl -d Ubuntu-18.04 -u atw bash -lc "bash /mnt/e/WSL_ENV/project/EdgeAI-ZU4EV_Claude/scripts/sync_windows_to_wsl.sh"
Write-Host "[sync] OK -> \\wsl.localhost\Ubuntu-18.04\home\atw\Edge_AI_Acc\claude\EdgeAI-ZU4EV_Claude"
