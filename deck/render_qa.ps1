# Render every slide of a .pptx to PNG via PowerPoint COM (authoritative
# renders for QA), and optionally export a PDF for Canvas.
#
# Usage:
#   powershell -File deck\render_qa.ps1 -Pptx deck\out\specimens\specimens.pptx -OutDir deck\out\specimens
#   powershell -File deck\render_qa.ps1 -Pptx deck\out\BZAN545_Final_Deck.pptx -OutDir deck\out\renders -Pdf deck\out\BZAN545_Final_Deck.pdf

param(
    [Parameter(Mandatory = $true)][string]$Pptx,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [string]$Pdf = "",
    [int]$Width = 1920
)

$ErrorActionPreference = "Stop"
$Pptx = (Resolve-Path $Pptx).Path
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$Height = [int]($Width * 9 / 16)

$pp = New-Object -ComObject PowerPoint.Application
try {
    # msoTrue=-1, msoFalse=0: ReadOnly, Untitled, WithWindow
    $pres = $pp.Presentations.Open($Pptx, -1, 0, 0)
    try {
        foreach ($slide in $pres.Slides) {
            $n = "{0:d2}" -f $slide.SlideIndex
            $png = Join-Path $OutDir "slide-$n.png"
            if (Test-Path $png) { Remove-Item $png -Force }
            $slide.Export($png, "PNG", $Width, $Height)
            Write-Output $png
        }
        if ($Pdf -ne "") {
            $PdfDir = Split-Path -Parent $Pdf
            if ($PdfDir -and -not (Test-Path $PdfDir)) {
                New-Item -ItemType Directory -Force $PdfDir | Out-Null
            }
            $PdfPath = Join-Path (Resolve-Path (Split-Path -Parent $Pdf)).Path (Split-Path -Leaf $Pdf)
            $pres.SaveAs($PdfPath, 32)   # ppSaveAsPDF
            Write-Output $PdfPath
        }
    }
    finally {
        $pres.Close()
    }
}
finally {
    $pp.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($pp)
}
