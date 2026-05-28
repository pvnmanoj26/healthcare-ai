#!/bin/bash
set -e

PROJECT_ID="healthcare-ai-manoj"
REGION="us-central1"
SERVICE_NAME="clinical-ai-app"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying Flask UI to Cloud Run..."
echo "   Project : ${PROJECT_ID}"
echo "   Region  : ${REGION}"
echo "   Service : ${SERVICE_NAME}"
echo ""

# Build and push using Cloud Build
gcloud builds submit \
  --tag ${IMAGE} \
  --project=${PROJECT_ID} \
  --file=deploy/Dockerfile.app \
  .

# Deploy to Cloud Run
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
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},BIGQUERY_DATASET=healthcare_ai,CLINICAL_API_BASE_URL=https://clinical-ai-api-230808425514.us-central1.run.app" \
  --service-account="clinical-ai-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project=${PROJECT_ID}

echo "✅ App deployment complete!"
