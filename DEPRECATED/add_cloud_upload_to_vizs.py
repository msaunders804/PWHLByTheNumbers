#!/usr/bin/env python3
"""
Utility script to add Google Drive upload capability to all visualizer scripts
Run this once to update all visualization scripts
"""

import os
import re

UPLOAD_CODE = '''
    # Auto-upload to Google Drive for mobile access
    try:
        sys.path.insert(0, os.path.join(parent_dir, 'src'))
        from utils.cloud_uploader import upload_visualization

        print("\\n[UPLOAD] Uploading to Google Drive for mobile access...")
        result = upload_visualization(file_path=output_file)

        if result.get('success'):
            print(f"[SUCCESS] {result.get('action', 'Uploaded')} to Google Drive!")
            print(f"[MOBILE] Access on phone: {result.get('web_view_link', 'Check Google Drive app')}")
        elif 'not enabled' in result.get('error', '').lower():
            print("[INFO] Google Drive upload disabled (enable in config.py)")
        else:
            print(f"[WARN] Upload skipped: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"[WARN] Cloud upload unavailable: {e}")
'''

VIZ_SCRIPTS = [
    'src/visualizers/skater_leaders_viz.py',
    'src/visualizers/goalie_leaders_viz.py',
    'src/visualizers/toi_leaders_viz.py',
    'src/visualizers/top_attendance_viz.py',
    'src/visualizers/weekly_lineup_viz.py',
    # standings_viz.py already updated
]


def add_upload_to_script(script_path):
    """Add Google Drive upload code to a visualizer script"""

    if not os.path.exists(script_path):
        print(f"[SKIP] Not found: {script_path}")
        return False

    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if already has upload code
    if 'cloud_uploader' in content:
        print(f"[OK] Already updated: {script_path}")
        return True

    # Find the pattern: plt.savefig(...) followed by print, then plt.close()
    # We want to insert the upload code between plt.close() and return statement

    pattern = r'(plt\.close\(\))\s*\n(\s*)(return output_file)'

    if not re.search(pattern, content):
        print(f"[WARN] Could not find insertion point in: {script_path}")
        return False

    # Insert the upload code
    replacement = r'\1\n\2' + UPLOAD_CODE.strip().replace('\n', '\n' + r'\2') + '\n\n\2\3'
    updated_content = re.sub(pattern, replacement, content)

    # Write back
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)

    print(f"[UPDATED] {script_path}")
    return True


def main():
    print("="*70)
    print("Adding Google Drive Upload to All Visualizers")
    print("="*70)

    success_count = 0
    for script in VIZ_SCRIPTS:
        if add_upload_to_script(script):
            success_count += 1
        print()

    print("="*70)
    print(f"[DONE] Updated {success_count}/{len(VIZ_SCRIPTS)} scripts")
    print("="*70)
    print("\nNext steps:")
    print("1. Follow GOOGLE_DRIVE_SETUP.md to configure credentials")
    print("2. Run any visualizer script to test the upload")
    print("3. Check your Google Drive folder on your phone!")


if __name__ == "__main__":
    main()
