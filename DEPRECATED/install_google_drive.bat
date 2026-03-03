@echo off
REM Quick installer for Google Drive dependencies

echo ====================================================================
echo Installing Google Drive Libraries for PWHL Analytics
echo ====================================================================
echo.

echo Installing required packages...
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

echo.
echo ====================================================================
echo Installation Complete!
echo ====================================================================
echo.
echo Next steps:
echo 1. Read GOOGLE_DRIVE_SETUP.md for detailed setup instructions
echo 2. Set up Google Cloud project and download credentials
echo 3. Place credentials at: credentials/google_drive_credentials.json
echo 4. Update config.py with your folder ID
echo 5. Run: python src/utils/cloud_uploader.py --type standings
echo.
echo See SETUP_SUMMARY.md for quick overview!
echo.

pause
