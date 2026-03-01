# Google Drive Auto-Upload Setup Guide

This guide will help you set up automatic uploading of PWHL visualizations to Google Drive, so they sync to your phone for easy TikTok posting.

## Overview

Once configured, every time you generate a visualization (standings, player leaders, etc.), it will automatically upload to a Google Drive folder that syncs to your phone. Just open the Google Drive app and your latest viz is ready to post!

## Setup Steps

### 1. Install Required Libraries

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 2. Create Google Cloud Project & Enable Drive API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing):
   - Click the project dropdown at the top
   - Click "New Project"
   - Name it "PWHL Analytics" or similar
   - Click "Create"

3. Enable Google Drive API:
   - In the search bar, type "Google Drive API"
   - Click on "Google Drive API"
   - Click "Enable"

### 3. Create OAuth 2.0 Credentials

1. Go to [Credentials Page](https://console.cloud.google.com/apis/credentials)
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure OAuth consent screen:
   - User Type: **External**
   - Click "Create"
   - Fill in required fields:
     - App name: "PWHL Analytics"
     - User support email: Your email
     - Developer contact: Your email
   - Click "Save and Continue"
   - Scopes: Skip this (click "Save and Continue")
   - Test users: Add your Google email address
   - Click "Save and Continue"

4. Create OAuth Client ID:
   - Application type: **Desktop app**
   - Name: "PWHL Desktop Client"
   - Click "Create"

5. Download credentials:
   - Click the download button (⬇️) next to your new OAuth client
   - This downloads a JSON file

### 4. Set Up Project Credentials

1. Create credentials folder in your project:
   ```bash
   mkdir credentials
   ```

2. Move the downloaded JSON file:
   - Rename it to `google_drive_credentials.json`
   - Move it to `credentials/google_drive_credentials.json`

3. Add to `.gitignore` (to keep credentials private):
   ```bash
   echo "credentials/" >> .gitignore
   ```

### 5. Create Google Drive Folder

1. Open [Google Drive](https://drive.google.com)
2. Create a new folder called "PWHL Visualizations" (or any name you like)
3. Open the folder
4. Look at the URL - it will look like:
   ```
   https://drive.google.com/drive/folders/1a2b3c4d5e6f7g8h9i0j
                                          ^^^^^^^^^^^^^^^^^
                                          This is your folder ID
   ```
5. Copy the folder ID (the random string after `/folders/`)

### 6. Configure Your Project

Edit `config.py` and update:

```python
# Google Drive Settings
GOOGLE_DRIVE_ENABLED = True  # Change to True
GOOGLE_DRIVE_FOLDER_ID = "YOUR_FOLDER_ID_HERE"  # Paste your folder ID
```

### 7. First-Time Authentication

Run the uploader for the first time:

```bash
python src/utils/cloud_uploader.py --type standings
```

This will:
1. Open your browser for authentication
2. Ask you to sign in to your Google account
3. Ask you to grant permissions to the app
4. Save authentication token for future use

**Important**:
- Use the same Google account where you created the Drive folder
- You'll see a warning that the app isn't verified - click "Advanced" then "Go to PWHL Analytics (unsafe)"
- This is normal for personal projects

### 8. Install Google Drive on Your Phone

1. Download Google Drive app:
   - [iOS App Store](https://apps.apple.com/us/app/google-drive/id507754991)
   - [Android Play Store](https://play.google.com/store/apps/details?id=com.google.android.apps.docs)

2. Sign in with the same Google account

3. The "PWHL Visualizations" folder will sync automatically

## Usage

### Automatic Upload (Recommended)

Once configured, visualizations automatically upload when created:

```bash
# Generate standings - auto-uploads to Drive
python src/visualizers/standings_viz.py

# Output shows:
# Visualization saved to: outputs/visualizations/pwhl_standings_20260106.png
# 📤 Uploading to Google Drive for mobile access...
# ✅ Uploaded to Google Drive!
# 📱 Access on phone: https://drive.google.com/...
```

### Manual Upload

Upload any visualization manually:

```bash
# Upload latest standings viz
python src/utils/cloud_uploader.py --type standings

# Upload specific file
python src/utils/cloud_uploader.py --file outputs/visualizations/pwhl_standings_20260106.png
```

### From Your Phone

1. Open Google Drive app
2. Navigate to "PWHL Visualizations" folder
3. Your latest visualization is there!
4. Tap to download or share directly to TikTok

## Workflow for TikTok Posting

1. **On Computer**: Generate visualization
   ```bash
   python src/visualizers/standings_viz.py
   ```

2. **Automatic**: File uploads to Google Drive

3. **On Phone**:
   - Open Google Drive app
   - Go to "PWHL Visualizations" folder
   - Tap the latest image
   - Tap share icon → TikTok
   - Add your voiceover/commentary
   - Post!

## Troubleshooting

### "Credentials not found" error
- Make sure `credentials/google_drive_credentials.json` exists
- Check the file path is correct

### "Authentication failed" error
- Delete `credentials/google_drive_token.json`
- Run the uploader again to re-authenticate

### "Upload failed: File not found" error
- Make sure the visualization was created successfully
- Check the `outputs/visualizations/` folder

### "Folder ID invalid" error
- Double-check your folder ID in `config.py`
- Make sure you copied the full ID from the Drive URL

### Files not syncing to phone
- Check you're signed into the same Google account
- Make sure you have internet connection
- Try refreshing the Drive app (pull down to refresh)

## Alternative: Quick Share Method

If you don't want to set up Google Drive API, you can use this simpler approach:

1. Save visualizations to a folder that's already syncing with Google Drive/Dropbox/OneDrive
2. Edit `config.py` to change output directory:
   ```python
   # In your visualization scripts, change output_dir to:
   # Windows: C:/Users/YourName/Google Drive/PWHL
   # Mac: /Users/YourName/Google Drive/PWHL
   ```

This is less automated but requires zero setup!

## Support

If you run into issues, check:
- [Google Drive API Documentation](https://developers.google.com/drive/api/v3/about-sdk)
- [OAuth 2.0 Setup Guide](https://developers.google.com/identity/protocols/oauth2)

## Privacy & Security

- Your credentials are stored locally in the `credentials/` folder
- Never commit credentials to git (they're in `.gitignore`)
- The OAuth token expires and can be revoked anytime from [Google Account Settings](https://myaccount.google.com/permissions)
- Files are uploaded to YOUR Google Drive - you have full control
