Write-Host "===== HedgeBot Server Test Suite =====" -ForegroundColor Cyan

# TEST 1: HEALTH CHECK
Write-Host "`n[1] HEALTH CHECK" -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing
    Write-Host "OK: Server is running" -ForegroundColor Green
    Write-Host $health.Content
} catch {
    Write-Host "FAIL: Server not responding" -ForegroundColor Red
    exit
}

# TEST 2: REGISTER USER
Write-Host "`n[2] REGISTER USER" -ForegroundColor Yellow
try {
    $regBody = @{
        username = "testuser"
        email = "test@example.com"
        password = "test123"
    } | ConvertTo-Json

    $regResponse = Invoke-WebRequest -Uri http://localhost:8000/register `
      -Method POST `
      -ContentType "application/json" `
      -Body $regBody `
      -UseBasicParsing

    $regData = $regResponse.Content | ConvertFrom-Json
    if ($regData.user_id) {
        Write-Host "OK: User registered" -ForegroundColor Green
        Write-Host "User ID: $($regData.user_id)"
        $token = $regData.access_token
    } else {
        Write-Host "FAIL: Registration failed" -ForegroundColor Red
        exit
    }
} catch {
    Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit
}

# TEST 3: LOGIN USER
Write-Host "`n[3] LOGIN USER" -ForegroundColor Yellow
try {
    $loginBody = @{
        email = "test@example.com"
        password = "test123"
    } | ConvertTo-Json

    $loginResponse = Invoke-WebRequest -Uri http://localhost:8000/login `
      -Method POST `
      -ContentType "application/json" `
      -Body $loginBody `
      -UseBasicParsing

    $loginData = $loginResponse.Content | ConvertFrom-Json
    if ($loginData.user_id) {
        Write-Host "OK: Login successful" -ForegroundColor Green
    } else {
        Write-Host "FAIL: Login failed" -ForegroundColor Red
        exit
    }
} catch {
    Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

# TEST 4: GET CURRENT USER
Write-Host "`n[4] GET CURRENT USER (WITH TOKEN)" -ForegroundColor Yellow
try {
    $meResponse = Invoke-WebRequest -Uri http://localhost:8000/me `
      -Method GET `
      -Headers @{"Authorization" = "Bearer $token"} `
      -UseBasicParsing

    $meData = $meResponse.Content | ConvertFrom-Json
    if ($meData.username) {
        Write-Host "OK: Get user successful" -ForegroundColor Green
        Write-Host "Username: $($meData.username)"
        Write-Host "Email: $($meData.email)"
    } else {
        Write-Host "FAIL: Get user failed" -ForegroundColor Red
    }
} catch {
    Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

# TEST 5: WRONG PASSWORD
Write-Host "`n[5] LOGIN WITH WRONG PASSWORD (SHOULD FAIL)" -ForegroundColor Yellow
try {
    $wrongBody = @{
        email = "test@example.com"
        password = "wrongpassword"
    } | ConvertTo-Json

    $wrongResponse = Invoke-WebRequest -Uri http://localhost:8000/login `
      -Method POST `
      -ContentType "application/json" `
      -Body $wrongBody `
      -UseBasicParsing -ErrorAction SilentlyContinue

    if ($wrongResponse.Content -like "*Invalid*") {
        Write-Host "OK: Correctly rejected wrong password" -ForegroundColor Green
    }
} catch {
    Write-Host "OK: Correctly rejected wrong password" -ForegroundColor Green
}

# TEST 6: NO TOKEN
Write-Host "`n[6] GET USER WITHOUT TOKEN (SHOULD FAIL)" -ForegroundColor Yellow
try {
    $noTokenResponse = Invoke-WebRequest -Uri http://localhost:8000/me `
      -Method GET `
      -UseBasicParsing -ErrorAction Stop
    Write-Host "FAIL: Should require token" -ForegroundColor Red
} catch {
    Write-Host "OK: Correctly requires authentication" -ForegroundColor Green
}

Write-Host "`n===== ALL TESTS COMPLETED =====" -ForegroundColor Green