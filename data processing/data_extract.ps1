<# Create directories
New-Item -ItemType Directory -Force -Path "raw_data\temp"

# Download all teams
$teamIds = @(1, 2, 3, 4, 5, 6, 8, 9)

foreach ($teamId in $teamIds) {
    Write-Host "Downloading team $teamId..."
    curl "https://lscluster.hockeytech.com/feed/?feed=modulekit&view=roster&key=446521baf8c38984&fmt=json&client_code=pwhl&lang=en&league_id=1&season_id=8&team_id=$teamId" -o "raw_data\temp\team_$teamId.json"
    Start-Sleep -Seconds 1
}

Write-Host "All teams downloaded!"#>

# Create directories
New-Item -ItemType Directory -Force -Path "raw_data"

Write-Host "=== Downloading PWHL Data ===" -ForegroundColor Green

# Skater stats
Write-Host "`n[1/4] Downloading skater stats..." -ForegroundColor Cyan
curl "https://lscluster.hockeytech.com/feed/index.php?feed=statviewfeed&view=players&season=8&team=all&position=skaters&rookies=0&statsType=standard&rosterstatus=undefined&site_id=0&league_id=1&lang=en&division=-1&conference=-1&key=446521baf8c38984&client_code=pwhl&league_id=1&limit=500&sort=points&league_id=1&lang=en&division=-1&conference=-1" -o "raw_data\skaters.json"
Start-Sleep 1

# Goalie stats
Write-Host "[2/4] Downloading goalie stats..." -ForegroundColor Cyan
curl "https://lscluster.hockeytech.com/feed/index.php?feed=statviewfeed&view=players&season=8&team=all&position=goalies&rookies=0&statsType=standard&rosterstatus=undefined&site_id=0&first=0&limit=500&sort=gaa&league_id=1&lang=en&division=-1&conference=-1&qualified=all&key=446521baf8c38984&client_code=pwhl&league_id=1" -o "raw_data\goalies.json"

# Schedule
Write-Host "[3/4] Downloading schedule..." -ForegroundColor Cyan
curl "https://lscluster.hockeytech.com/feed/?feed=modulekit&view=scorebar&key=446521baf8c38984&fmt=json&client_code=pwhl&lang=en&league_id=1&season_id=8&numberofdaysahead=365&numberofdaysback=365" -o "raw_data\schedule.json"
Start-Sleep 1

# Standings
Write-Host "[4/4] Downloading team standings..." -ForegroundColor Cyan
curl "https://lscluster.hockeytech.com/feed/index.php?feed=modulekit&view=statviewtype&stat=conference&type=standings&season_id=8&key=446521baf8c38984&client_code=pwhl" -o "raw_data\standings.json"

Write-Host "`n✅ All data downloaded successfully!" -ForegroundColor Green
Write-Host "`nFiles created:"
Get-ChildItem raw_data\*.json | ForEach-Object { Write-Host "  - $($_.Name)" }

Write-Host "`n[6/6] Prettifying JSON files..." -ForegroundColor Cyan

$jsonFiles = Get-ChildItem raw_data\*.json

foreach ($file in $jsonFiles) {
    Write-Host "  - Processing $($file.Name)..."
    try {
        # Read file content
        $content = Get-Content $file.FullName -Raw
        
        # Remove JavaScript wrapper patterns:
        # Pattern 1: ([{...}])
        # Pattern 2: callback([{...}])
        # Pattern 3: angular.callbacks._X({...})
        
        if ($content -match '^\s*\(\s*\[') {
            # Pattern: ([...])
            $content = $content -replace '^\s*\(\s*', '' -replace '\s*\)\s*$', ''
            Write-Host "Removed () wrapper" -ForegroundColor Gray
        }
        
        if ($content -match 'angular\.callbacks\._\d+\(') {
            # Pattern: angular.callbacks._2({...})
            $content = $content -replace '^angular\.callbacks\._\d+\(', '' -replace '\)$', ''
            Write-Host "Removed angular.callbacks wrapper" -ForegroundColor Gray
        }
        
        if ($content -match '^\w+\(') {
            # Pattern: someCallback({...})
            $content = $content -replace '^\w+\(', '' -replace '\)$', ''
            Write-Host "Removed callback wrapper" -ForegroundColor Gray
        }
        
        # Parse and prettify JSON
        $jsonObject = $content | ConvertFrom-Json
        $prettyJson = $jsonObject | ConvertTo-Json -Depth 100
        
        # Save back to file
        $prettyJson | Set-Content $file.FullName -Encoding UTF8
        
        Write-Host "Cleaned and formatted" -ForegroundColor Green
        
    } catch {
        Write-Host " Error: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host " File may need manual inspection" -ForegroundColor Yellow
    }
}

Write-Host " All data downloaded and cleaned!" -ForegroundColor Green
Write-Host "`nFiles created:"
Get-ChildItem raw_data\*.json | ForEach-Object { 
    $size = [math]::Round($_.Length/1KB, 2)
    Write-Host "  - $($_.Name) ($size KB)" 
}
Write-Host "`nLogos:"
Get-ChildItem assets\logos\*.png | ForEach-Object { Write-Host "  - $($_.Name)" }
