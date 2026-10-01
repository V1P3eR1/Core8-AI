# Core8-AI Business Laptop Bootstrap Script
# Run in PowerShell

Write-Host "=== Core8-AI Business Setup Bootstrap ===" -ForegroundColor Cyan

$username = $env:USERNAME

# Create Core8-AI folder structure
Write-Host "`n[1] Creating Core8-AI folder structure..." -ForegroundColor Yellow

$folders = @(
    "$env:USERPROFILE\Documents\Core8-AI",
    "$env:USERPROFILE\Projects\Core8-AI",
    "$env:USERPROFILE\Projects\Core8-AI\agents",
    "$env:USERPROFILE\Projects\Core8-AI\rag-systems",
    "$env:USERPROFILE\Projects\Core8-AI\client-deliverables",
    "$env:USERPROFILE\Projects\Core8-AI\internal-tools",
    "$env:USERPROFILE\Desktop\Core8-AI-Work",
    "$env:USERPROFILE\.claude\skills"
)

foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        Write-Host "Created: $folder" -ForegroundColor Green
    } else {
        Write-Host "Exists: $folder" -ForegroundColor Gray
    }
}

Write-Host "`n[2] Claude Code installation command:" -ForegroundColor Yellow
Write-Host "irm https://claude.ai/install.ps1 | iex" -ForegroundColor White

Write-Host "`n[3] MCP Config:" -ForegroundColor Yellow
Write-Host "Copy claude_desktop_config.json to %APPDATA%\Claude\" -ForegroundColor White
Write-Host "Replace YOUR_USERNAME and GitHub PAT!" -ForegroundColor Red

Write-Host "`n[4] Security reminders:" -ForegroundColor Yellow
Write-Host "- Least privilege on all tokens and MCP scopes"
Write-Host "- Secrets only in password manager"
Write-Host "- Daily encrypted backup of Core8-AI folders"
Write-Host "- Separate accounts for development vs finance"

Write-Host "`n=== Core8-AI Bootstrap complete ===" -ForegroundColor Cyan
Write-Host "Review README-SETUP-Core8-AI.md for full details." -ForegroundColor Cyan
