# Security Check Script
Write-Host "Running Security Checks..." -ForegroundColor Cyan

# Check if bandit is installed
if (-not (Get-Command bandit -ErrorAction SilentlyContinue)) {
    Write-Host "Bandit is not installed. Installing..." -ForegroundColor Yellow
    pip install bandit
}

# Run Bandit
Write-Host "Running Bandit (AST-based security analysis)..." -ForegroundColor Cyan
bandit -r . -c pyproject.toml -f txt -o bandit_report.txt --exit-zero
if ($LASTEXITCODE -ne 0) {
    Write-Host "Bandit found issues! Check bandit_report.txt" -ForegroundColor Red
} else {
    Write-Host "Bandit check passed (or exit-zero used)." -ForegroundColor Green
}

# Check if pip-audit is installed
if (-not (Get-Command pip-audit -ErrorAction SilentlyContinue)) {
    Write-Host "pip-audit is not installed. Installing..." -ForegroundColor Yellow
    pip install pip-audit
}

# Run pip-audit
Write-Host "Running pip-audit (Dependency vulnerability check)..." -ForegroundColor Cyan
pip-audit
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip-audit found vulnerabilities!" -ForegroundColor Red
} else {
    Write-Host "pip-audit check passed." -ForegroundColor Green
}

Write-Host "Security Checks Completed." -ForegroundColor Cyan
