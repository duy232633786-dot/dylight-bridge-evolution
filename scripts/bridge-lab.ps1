param(
    [ValidateSet("codex", "claude", "opencode", "antigravity")]
    [string]$Agent = "codex"
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $ProjectRoot
try {
    python -m bridge_evolution.cli lab validate
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m bridge_evolution.cli lab status
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m bridge_evolution.cli lab brief --agent $Agent
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
