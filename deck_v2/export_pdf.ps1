# Export deck.html to deck.pdf — the podium backup and the Canvas submission.
#
# Uses headless Chrome, which is already on this machine. (The frontend-slides
# skill ships a Playwright exporter, but that needs Node.js, which is not
# installed here.) The deck's @media print rules put one 16:9 slide per page
# and force every reveal to its final state, so the PDF loses no content.
#
# Usage:  powershell -File deck_v2\export_pdf.ps1
#
# Requires the deck to be reachable over HTTP: browsers refuse to load the
# Google Fonts and the local chart images consistently from a file:// path.

$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$out    = Join-Path $here "deck.pdf"
$port   = 8791

$chrome = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $chrome) { throw "Chrome not found. Install Chrome or Edge and update this script." }

# serve deck_v2/ so assets/ and the web fonts resolve
$server = Start-Process -FilePath "python" -ArgumentList "-m","http.server",$port `
    -WorkingDirectory $here -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2

try {
    if (Test-Path $out) { Remove-Item $out }
    & $chrome --headless=new --disable-gpu --no-first-run --no-pdf-header-footer `
        --user-data-dir="$env:TEMP\chrome-pdf-profile" `
        --virtual-time-budget=20000 `
        --print-to-pdf="$out" "http://localhost:$port/deck.html" 2>$null
    Start-Sleep -Seconds 2
} finally {
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
}

if (Test-Path $out) {
    $mb = (Get-Item $out).Length / 1MB
    Write-Output ("[pdf] {0}  ({1:N2} MB)" -f $out, $mb)
} else {
    throw "PDF was not produced."
}
