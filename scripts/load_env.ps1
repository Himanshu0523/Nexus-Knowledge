param(
    [string]$EnvFile = ".env.example"
)

if (-not (Test-Path $EnvFile)) {
    Write-Error "Environment file $EnvFile not found"
    exit 1
}

Write-Host "Loading environment from $EnvFile" -ForegroundColor Green

Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $name = $Matches[1].Trim()
        $value = $Matches[2].Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

Write-Host "Environment loaded successfully!" -ForegroundColor Green
Write-Host "APP_ENV: $env:APP_ENV"
Write-Host "DATABASE_URL: $env:DATABASE_URL"
