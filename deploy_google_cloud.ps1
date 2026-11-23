# Deploy the Unified Test Orchestration website to Google Cloud Run.
# Run from this folder after: gcloud auth login

$ErrorActionPreference = 'Stop'

$service = 'unified-test-orchestration'
$region = 'us-central1'

Write-Host 'Enabling required Google Cloud APIs...'
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

Write-Host 'Deploying to Cloud Run (this builds the Dockerfile via Cloud Build)...'
gcloud run deploy $service `
  --source . `
  --region $region `
  --platform managed `
  --allow-unauthenticated `
  --set-env-vars 'API_BASE_URL=http://127.0.0.1:8001,UI_BASE_URL=http://127.0.0.1:8001'

Write-Host 'Fetching the public URL...'
gcloud run services describe $service --region $region --format 'value(status.url)'
