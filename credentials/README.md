# Google Service Account Credentials

## Setup Instructions

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable Required APIs:**
   - Google Sheets API
   - Google Drive API

3. **Create Service Account:**
   - Navigate to IAM & Admin → Service Accounts
   - Click "Create Service Account"
   - Name: `marketbel-ingestion-service`
   - Grant role: `Editor` (or minimum required permissions)

4. **Generate Credentials:**
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" → "Create new key"
   - Choose JSON format
   - Download the file

5. **Install Credentials:**
   - Rename the downloaded file to `google-credentials.json`
   - Place it in this directory: `/credentials/google-credentials.json`
   - Verify permissions: file should be readable only by the worker container

6. **Share Google Sheets:**
   - Open your Google Sheet
   - Click "Share"
   - Add the service account email (found in the JSON file: `client_email`)
   - Grant "Viewer" or "Editor" access as needed

## Security Notes

- **Never commit** `google-credentials.json` to git
- The credentials directory is included in `.gitignore`
- In production, mount credentials as read-only volume
- Rotate service account keys regularly (recommended: every 90 days)
- Use least privilege principle: grant only necessary permissions

## Docker Volume Mounting

The credentials are mounted in `docker-compose.yml` as:

```yaml
volumes:
  - ./credentials:/app/credentials:ro  # Read-only mount
```

## Verification

Test authentication with:

```bash
docker-compose exec worker python -c "import gspread; from oauth2client.service_account import ServiceAccountCredentials; creds = ServiceAccountCredentials.from_json_keyfile_name('/app/credentials/google-credentials.json', ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']); print('Authentication successful!')"
```
