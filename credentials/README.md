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
   - **Set restrictive file permissions** (important for security):
     ```bash
     chmod 600 credentials/google-credentials.json  # Owner read/write only
     ```
   - Verify permissions: file should be `-rw-------` (600), readable/writable by owner only

6. **Share Google Sheets:**
   - Open your Google Sheet
   - Click "Share"
   - Add the service account email (found in the JSON file: `client_email`)
   - Grant "Viewer" or "Editor" access as needed

## Security Notes

### File Protection

- **Never commit** `google-credentials.json` to git
  - File is explicitly ignored in `.gitignore` (line 93)
  - Credentials directory pattern is ignored (line 89: `credentials/*`)
  - Only `README.md` is tracked in git
- **Set restrictive file permissions:**
  ```bash
  chmod 600 credentials/google-credentials.json  # Owner read/write only
  ```
- **In production:** Mount credentials as read-only volume (`:ro` flag in docker-compose.yml)

### Access Control

- **Use least privilege principle:** Grant service account only necessary permissions
  - Minimum required: "Viewer" role on Google Sheets (not "Editor" unless write access needed)
  - Do not grant broad Google Cloud permissions (e.g., avoid "Owner" or "Editor" at project level)
- **Service Account Isolation:**
  - Use dedicated service account for ingestion (not shared with other services)
  - Limit to specific Google Cloud project (avoid cross-project access)

### Key Rotation

- **Rotate service account keys regularly:**
  - Recommended: every 90 days
  - Maximum: every 180 days (Google's recommended maximum)
- **Before rotation:**
  1. Generate new key
  2. Deploy new credentials
  3. Verify authentication works
  4. Revoke old key in Google Cloud Console
  5. Monitor for any authentication errors

### Monitoring & Auditing

- **Monitor authentication failures** in application logs
- **Set up alerts** for unauthorized access attempts
- **Review service account usage** in Google Cloud Console Audit Logs
- **Track key creation/rotation dates** (consider maintaining a rotation schedule)

### Additional Security Best Practices

- **Environment-specific credentials:** Use different service accounts for dev/staging/prod
- **Secrets management:** In production, consider using:
  - Google Secret Manager
  - HashiCorp Vault
  - Kubernetes Secrets
  - AWS Secrets Manager / Azure Key Vault
- **Never log credentials:** Ensure logging configuration excludes credential file contents
- **Backup securely:** If backing up credentials, encrypt them and store in secure location

## Docker Volume Mounting

The credentials are mounted in `docker-compose.yml` as:

```yaml
volumes:
  - ./credentials:/app/credentials:ro  # Read-only mount
```

## Verification

### Verify File Permissions

Check that credentials file has restrictive permissions:

```bash
ls -la credentials/google-credentials.json
# Should show: -rw------- (600 permissions)
```

If permissions are incorrect, fix them:

```bash
chmod 600 credentials/google-credentials.json
```

### Test Authentication

Test authentication using the modern gspread API (same method used by the parser):

```bash
docker-compose exec worker python -c "import gspread; client = gspread.service_account(filename='/app/credentials/google-credentials.json'); print('✅ Authentication successful!')"
```

Or test from local environment (if gspread is installed):

```bash
python -c "import gspread; client = gspread.service_account(filename='credentials/google-credentials.json'); print('✅ Authentication successful!')"
```

### Verify Git Ignore

Ensure credentials are not tracked by git:

```bash
git check-ignore -v credentials/google-credentials.json
# Should show: .gitignore:93:google-credentials.json

git ls-files credentials/google-credentials.json
# Should return nothing (file not in git)
```

### Verify Docker Volume Mount

Check that credentials are mounted as read-only in container:

```bash
docker-compose exec worker ls -la /app/credentials/
# Should show google-credentials.json with read-only permissions

dd
```
