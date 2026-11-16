$ErrorActionPreference = "Stop"

$source = Get-Content -LiteralPath (Join-Path $PSScriptRoot "bookmarklet.js") -Raw
$encoded = [System.Uri]::EscapeDataString($source)
$output = "javascript:$encoded"
$target = Join-Path $PSScriptRoot "bookmarklet.txt"
Set-Content -LiteralPath $target -Value $output -NoNewline -Encoding ASCII
Write-Output "Wrote $target ($($output.Length) characters)."
