#!/bin/bash
set -e

PROJECT_ID="healthcare-ai-manoj"
REGION="us-central1"
SERVICE_NAME="clinical-ai-api"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying FastAPI Backend to Cloud Run..."
echo "   Project : ${PROJECT_ID}"
echo "   Region  : ${REGION}"
echo "   Service : ${SERVICE_NAME}"
echo ""

# Build and push using Cloud Build
cp deploy/Dockerfile.api Dockerfile
gcloud builds submit \
  --tag ${IMAGE} \
  --project=${PROJECT_ID} \
  .
rm -f Dockerfile

# Deploy to Cloud Run
gcloud beta run deploy ${SERVICE_NAME} \
  --image ${IMAGE} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 10 \
  --set-secrets="ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,UPSTASH_VECTOR_REST_URL=UPSTASH_VECTOR_REST_URL:latest,UPSTASH_VECTOR_REST_TOKEN=UPSTASH_VECTOR_REST_TOKEN:latest" \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},BIGQUERY_DATASET=healthcare_ai" \
  --project=${PROJECT_ID}

echo "✅ API deployment complete!"
