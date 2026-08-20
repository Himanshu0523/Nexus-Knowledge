# Test streaming with PowerShell
Write-Host "Testing Streaming API..." -ForegroundColor Green

$conversationId = "conv_stream_$(Get-Date -Format 'yyyyMMddHHmmss')"

$body = @{
    conversation_id = $conversationId
    message = "Explain machine learning"
    metadata = @{
        user_id = "powershell_user"
        client = "powershell"
    }
} | ConvertTo-Json

Write-Host "`nSending streaming request..." -ForegroundColor Yellow

try {
    $response = Invoke-WebRequest `
        -Uri "http://localhost:8000/api/v1/chat/stream" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -TimeoutSec 60

    Write-Host "Response received!" -ForegroundColor Green
    Write-Host $response.Content
}
catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
