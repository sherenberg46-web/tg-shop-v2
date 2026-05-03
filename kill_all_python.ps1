Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Output "Killing PID $($_.Id)"
    Stop-Process -Id $_.Id -Force
}
Get-Process node -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Output "Killing node PID $($_.Id)"
    Stop-Process -Id $_.Id -Force
}
Write-Output "All killed"
