# test_api.ps1
Write-Host "Testing Chatbot API..." -ForegroundColor Green

# Test 1: Basic request
Write-Host "`nTest 1: Basic request" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" `
        -Method POST `
        -ContentType "application/json" `
        -Body '{"conversation_id": "conv_123", "message": "Hello"}'
    
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}

# Test 2: With API key
Write-Host "`nTest 2: With API key" -ForegroundColor Yellow
try {
    $headers = @{
        "X-API-Key" = "sk_dev_key_123456789"
    }
    
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" `
        -Method POST `
        -ContentType "application/json" `
        -Headers $headers `
        -Body '{"conversation_id": "conv_123", "message": "Explain machine learning", "stream": false, "metadata": {"language": "en", "client": "powershell"}}'
    
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}

# Test 3: Invalid request (missing message)
Write-Host "`nTest 3: Invalid request (missing message)" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" `
        -Method POST `
        -ContentType "application/json" `
        -Body '{"conversation_id": "conv_123"}'
    
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Status Code: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
    $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
    $reader.BaseStream.Position = 0
    $reader.DiscardBufferedData()
    $responseBody = $reader.ReadToEnd()
    Write-Host "Response: $responseBody" -ForegroundColor Red
}

# Test 4: With Bearer token
Write-Host "`nTest 4: With Bearer token" -ForegroundColor Yellow
try {
    $headers = @{
        "Authorization" = "Bearer sk_dev_key_123456789"
    }
    
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" `
        -Method POST `
        -ContentType "application/json" `
        -Headers $headers `
        -Body '{"conversation_id": "conv_456", "message": "What is deep learning?"}'
    
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}

Write-Host "`nTests completed!" -ForegroundColor Green
