#!/bin/bash
# ─────────────────────────────────────────────
# deploy.sh — One-click Cloud Run deployment
# Run from: /Users/manojpotharlankavenkatanaga/Downloads/clinical_ai/
# ─────────────────────────────────────────────

set -e  # Exit immediately if a command fails

# ── CONFIG ──────────────────────────────────
PROJECT_ID="healthcare-ai-manoj"
REGION="us-central1"
SERVICE_NAME="clinical-app"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Starting deployment to Cloud Run..."
echo "   Project : ${PROJECT_ID}"
echo "   Region  : ${REGION}"
echo "   Service : ${SERVICE_NAME}"
echo ""

# ── STEP 1: Set GCP project ─────────────────
echo "📌 Step 1: Setting GCP project..."
gcloud config set project ${PROJECT_ID}

# ── STEP 2: Enable required APIs ────────────
echo "🔌 Step 2: Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  containerregistry.googleapis.com \
  --quiet

# ── STEP 3: Store secrets in Secret Manager ─
echo "🔐 Step 3: Setting up secrets in Secret Manager..."

store_secret() {
  local SECRET_NAME=$1
  local PROMPT=$2
  if ! gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
    echo -n "  Enter value for ${PROMPT}: "
    read -s SECRET_VALUE
    echo ""
    echo -n "${SECRET_VALUE}" | gcloud secrets create "${SECRET_NAME}" \
      --data-file=- \
      --replication-policy="automatic" \
      --project="${PROJECT_ID}"
    echo "  ✅ ${SECRET_NAME} created"
  else
    echo "  ℹ️  ${SECRET_NAME} already exists — skipping"
  fi
}

store_secret "ANTHROPIC_API_KEY"       "Anthropic API Key"
store_secret "UPSTASH_VECTOR_REST_URL" "Upstash Vector REST URL"
store_secret "UPSTASH_VECTOR_REST_TOKEN" "Upstash Vector REST Token"
store_secret "FLASK_SECRET_KEY"        "Flask Secret Key (any random string)"

# ── STEP 4: Build and push Docker image ─────
echo ""
echo "🐳 Step 4: Building and pushing Docker image..."
gcloud builds submit \
  --tag ${IMAGE} \
  --project=${PROJECT_ID} \
  .

echo "  ✅ Image pushed: ${IMAGE}"

# ── STEP 5: Deploy to Cloud Run ─────────────
echo ""
echo "☁️  Step 5: Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 10 \
  --set-secrets="ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,UPSTASH_VECTOR_REST_URL=UPSTASH_VECTOR_REST_URL:latest,UPSTASH_VECTOR_REST_TOKEN=UPSTASH_VECTOR_REST_TOKEN:latest,FLASK_SECRET_KEY=FLASK_SECRET_KEY:latest" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --service-account="clinical-ai-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project=${PROJECT_ID}

# ── DONE ────────────────────────────────────
echo ""
echo "✅ Deployment complete!"
echo "🌐 Your app is live at:"
gcloud run services describe ${SERVICE_NAME} \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --format="value(status.url)"
