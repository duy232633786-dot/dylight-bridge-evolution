$ErrorActionPreference = 'Stop'
$collectionSource = Join-Path $PSScriptRoot 'publication'
$collectionParent = 'D:\Obsidian Vault\DYLIGHT Bridge Evolution\Literature'
$collectionName = 'SAGE-EvoBridge Research 2026-09-23'
$collectionParentResolved = (Resolve-Path -LiteralPath $collectionParent).Path
$collectionDestination = [IO.Path]::GetFullPath((Join-Path $collectionParentResolved $collectionName))
if (-not $collectionDestination.StartsWith($collectionParentResolved + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Publication target escaped the authorized collection parent.'
}
$qa = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'qa_report.json') -Raw | ConvertFrom-Json
if ($qa.status -ne 'PASS') { throw 'Package QA must pass before publication.' }
$collectionManifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'publication_manifest.json') -Raw | ConvertFrom-Json
foreach ($entry in $collectionManifest.files) {
    $sourceFile = Join-Path $collectionSource $entry.path
    if ((Get-FileHash -LiteralPath $sourceFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw "Staged file changed after QA: $($entry.path)"
    }
}
$sourceFiles = @(Get-ChildItem -LiteralPath $collectionSource -File -Recurse)
# Kiểm toàn bộ đích trước khi ghi; tuyệt đối không ghi đè ghi chú đã có.
foreach ($sourceFile in $sourceFiles) {
    $relativeFile = [IO.Path]::GetRelativePath($collectionSource, $sourceFile.FullName)
    $targetFile = [IO.Path]::GetFullPath((Join-Path $collectionDestination $relativeFile))
    if (-not $targetFile.StartsWith($collectionDestination + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid target path.' }
    if (Test-Path -LiteralPath $targetFile) {
        if ((Get-FileHash -LiteralPath $targetFile).Hash -ne (Get-FileHash -LiteralPath $sourceFile.FullName).Hash) {
            throw "Existing different file must be preserved: $targetFile"
        }
    }
}
$copied = 0
foreach ($sourceFile in $sourceFiles) {
    $relativeFile = [IO.Path]::GetRelativePath($collectionSource, $sourceFile.FullName)
    $targetFile = Join-Path $collectionDestination $relativeFile
    if (-not (Test-Path -LiteralPath $targetFile)) {
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($targetFile)) | Out-Null
        Copy-Item -LiteralPath $sourceFile.FullName -Destination $targetFile
        $copied += 1
    }
}
$verified = @()
foreach ($sourceFile in $sourceFiles) {
    $relativeFile = [IO.Path]::GetRelativePath($collectionSource, $sourceFile.FullName)
    $targetFile = Join-Path $collectionDestination $relativeFile
    $sourceHash = (Get-FileHash -LiteralPath $sourceFile.FullName -Algorithm SHA256).Hash
    $targetHash = (Get-FileHash -LiteralPath $targetFile -Algorithm SHA256).Hash
    if ($sourceHash -ne $targetHash) { throw "Published hash mismatch: $relativeFile" }
    $verified += @{ path = $relativeFile; sha256 = $targetHash.ToLowerInvariant() }
}
$receipt = @{
    status = 'PUBLISHED_AND_HASH_VERIFIED'
    destination = $collectionDestination
    copied_new_files = $copied
    verified_files = $verified.Count
    overwritten_existing_files = 0
    scope = 'Additive collection directory only'
    files = $verified
}
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'publication_receipt.json') -Encoding utf8
$qa.publication_status = 'PUBLISHED_AND_HASH_VERIFIED'
$qa | Add-Member -NotePropertyName 'published_destination' -NotePropertyValue $collectionDestination -Force
$qa | Add-Member -NotePropertyName 'published_files_hash_verified' -NotePropertyValue $verified.Count -Force
$qa | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'qa_report.json') -Encoding utf8
@{ status = $receipt.status; copied = $copied; verified = $verified.Count; destination = $collectionDestination } | ConvertTo-Json
