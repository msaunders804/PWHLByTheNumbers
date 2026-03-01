# Google Drive Auto-Upload - Setup Summary

## What Was Added

Your PWHL visualization pipeline now includes automatic Google Drive uploading for easy mobile access!

## Files Created/Modified

### New Files
1. **`src/utils/cloud_uploader.py`** - Google Drive upload utility
2. **`GOOGLE_DRIVE_SETUP.md`** - Detailed setup instructions
3. **`TIKTOK_WORKFLOW.md`** - TikTok posting workflow guide
4. **`add_cloud_upload_to_vizs.py`** - Utility script (already run)

### Modified Files
1. **`config.py`** - Added Google Drive settings
2. **All visualizer scripts** - Added auto-upload after generation:
   - `standings_viz.py` ✅
   - `skater_leaders_viz.py` ✅
   - `goalie_leaders_viz.py` ✅
   - `toi_leaders_viz.py` ✅
   - `weekly_lineup_viz.py` ✅
   - `top_attendance_viz.py` ✅

## Next Steps (One-Time Setup)

### 1. Install Google Libraries
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 2. Set Up Google Drive API
Follow the detailed instructions in **`GOOGLE_DRIVE_SETUP.md`**:
- Create Google Cloud project
- Enable Drive API
- Download OAuth credentials
- Place credentials in `credentials/google_drive_credentials.json`

### 3. Create Google Drive Folder
1. Go to Google Drive
2. Create folder "PWHL Visualizations"
3. Copy the folder ID from URL
4. Update `config.py`:
   ```python
   GOOGLE_DRIVE_ENABLED = True
   GOOGLE_DRIVE_FOLDER_ID = "your_folder_id_here"
   ```

### 4. First-Time Authentication
```bash
python src/utils/cloud_uploader.py --type standings
```
This will open browser for one-time authentication.

### 5. Install Google Drive on Phone
- Download Google Drive app
- Sign in with same account
- Folder syncs automatically!

## How It Works

### Before (Manual Process)
1. Generate visualization on computer
2. Find file in outputs folder
3. Email to yourself OR manually upload to cloud
4. Download on phone
5. Post to TikTok

### After (Streamlined Process)
1. Generate visualization on computer
2. **Automatically uploads to Google Drive**
3. Open Google Drive app on phone
4. Latest viz is already there!
5. Share directly to TikTok

## Daily Usage

```bash
# Generate any visualization
python src/visualizers/standings_viz.py

# Output shows:
# Visualization saved to: outputs/visualizations/pwhl_standings_20260106.png
# 📤 Uploading to Google Drive for mobile access...
# ✅ Uploaded to Google Drive!
# 📱 Access on phone: https://drive.google.com/...
```

Then on phone:
1. Open Google Drive app
2. Go to "PWHL Visualizations" folder
3. Tap latest image → Share → TikTok
4. Post!

## Benefits

✅ **Faster** - No manual upload/download steps
✅ **Automatic** - Uploads happen during viz generation
✅ **Mobile-ready** - Files sync to phone instantly
✅ **Organized** - All vizs in one folder
✅ **Reliable** - Google Drive handles syncing
✅ **Flexible** - Works with any device (iOS/Android)

## Alternative (If You Don't Want to Set Up API)

### Simple File Sync Method
1. Change output directory in viz scripts to a folder already syncing with cloud storage
2. Example: Save directly to `C:/Users/YourName/Google Drive/PWHL/`
3. No API setup needed, files auto-sync via Drive desktop app

Edit viz scripts to change output_dir:
```python
output_dir = "C:/Users/YourName/Google Drive/PWHL Visualizations"
```

## Troubleshooting

See **`GOOGLE_DRIVE_SETUP.md`** for detailed troubleshooting.

Common issues:
- Credentials not found → Check file path
- Authentication failed → Delete token, re-authenticate
- Files not syncing → Refresh Drive app, check account
- Upload disabled → Set `GOOGLE_DRIVE_ENABLED = True` in config.py

## Support Files

- **`GOOGLE_DRIVE_SETUP.md`** - Complete setup guide
- **`TIKTOK_WORKFLOW.md`** - Content ideas and posting tips
- **`config.py`** - Configuration settings
- **`src/utils/cloud_uploader.py`** - Upload code (can be used standalone)

## Testing

Before full setup, visualizations still work normally:
```bash
python src/visualizers/standings_viz.py
# Creates viz locally
# Shows: "Google Drive upload disabled (enable in config.py)"
# Still usable, just no auto-upload yet
```

After setup:
```bash
python src/visualizers/standings_viz.py
# Creates viz locally
# Uploads to Google Drive
# Prints Drive link
# Ready on phone!
```

## Privacy Note

- Your Google credentials stay on your computer
- Files upload to YOUR Google Drive only
- You control access and can revoke anytime
- Never commit credentials to git (automatically ignored)

---

**Ready to go?** Start with `GOOGLE_DRIVE_SETUP.md` for step-by-step instructions!
