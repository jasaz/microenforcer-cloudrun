#!/usr/bin/env bash
# =============================================================================
# GCP Setup Script — Workload Identity Federation + Infrastructure
# =============================================================================
# This script configures the GCP project for CI/CD deployments from GitHub
# Actions using Workload Identity Federation (keyless authentication).
#
# Prerequisites:
#   - gcloud CLI installed and authenticated with sufficient permissions
#   - The GCP project must already exist
#
# Usage:
#   chmod +x setup/setup-wif.sh
#   ./setup/setup-wif.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — Update these values as needed
# ---------------------------------------------------------------------------
PROJECT_ID="cloudrun-microenforcer"
REGION="asia-south1"
GITHUB_ORG="jasaz"
GITHUB_REPO="microenforcer-cloudrun"

# Resource names
SERVICE_ACCOUNT_NAME="github-deployer"
WIF_POOL_NAME="github-wif-pool"
WIF_PROVIDER_NAME="github-provider"
GAR_REPO_NAME="microenforcer-repo"

# Derived values
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "============================================="
echo " GCP Setup for Cloud Run + WIF"
echo " Project:  ${PROJECT_ID}"
echo " Region:   ${REGION}"
echo " GitHub:   ${GITHUB_ORG}/${GITHUB_REPO}"
echo "============================================="

# ---------------------------------------------------------------------------
# 1. Set the active project
# ---------------------------------------------------------------------------
echo ""
echo "[1/8] Setting active project..."
gcloud config set project "${PROJECT_ID}"

# ---------------------------------------------------------------------------
# 2. Enable required APIs
# ---------------------------------------------------------------------------
echo ""
echo "[2/8] Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  sts.googleapis.com

echo "APIs enabled successfully."

# ---------------------------------------------------------------------------
# 3. Create Artifact Registry repository
# ---------------------------------------------------------------------------
echo ""
echo "[3/8] Creating Artifact Registry repository..."
if gcloud artifacts repositories describe "${GAR_REPO_NAME}" \
    --location="${REGION}" --format="value(name)" 2>/dev/null; then
  echo "Repository '${GAR_REPO_NAME}' already exists, skipping."
else
  gcloud artifacts repositories create "${GAR_REPO_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Container images for microenforcer-cloudrun"
  echo "Repository '${GAR_REPO_NAME}' created."
fi

# ---------------------------------------------------------------------------
# 4. Create Service Account for GitHub Actions
# ---------------------------------------------------------------------------
echo ""
echo "[4/8] Creating service account..."
if gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" 2>/dev/null; then
  echo "Service account '${SERVICE_ACCOUNT_NAME}' already exists, skipping."
else
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
    --display-name="GitHub Actions Deployer" \
    --description="Used by GitHub Actions to deploy to Cloud Run via WIF"
  echo "Service account '${SERVICE_ACCOUNT_NAME}' created."
fi

# ---------------------------------------------------------------------------
# 5. Grant IAM roles to the Service Account
# ---------------------------------------------------------------------------
echo ""
echo "[5/8] Granting IAM roles to service account..."

ROLES=(
  "roles/run.admin"
  "roles/iam.serviceAccountUser"
  "roles/artifactregistry.writer"
)

for ROLE in "${ROLES[@]}"; do
  echo "  Granting ${ROLE}..."
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet
done

echo "IAM roles granted."

# ---------------------------------------------------------------------------
# 6. Create Workload Identity Pool
# ---------------------------------------------------------------------------
echo ""
echo "[6/8] Creating Workload Identity Pool..."
if gcloud iam workload-identity-pools describe "${WIF_POOL_NAME}" \
    --location="global" --format="value(name)" 2>/dev/null; then
  echo "WIF Pool '${WIF_POOL_NAME}' already exists, skipping."
else
  gcloud iam workload-identity-pools create "${WIF_POOL_NAME}" \
    --location="global" \
    --display-name="GitHub Actions Pool" \
    --description="Workload Identity Pool for GitHub Actions OIDC"
  echo "WIF Pool '${WIF_POOL_NAME}' created."
fi

# ---------------------------------------------------------------------------
# 7. Create Workload Identity Provider (OIDC — GitHub)
# ---------------------------------------------------------------------------
echo ""
echo "[7/8] Creating Workload Identity Provider..."
if gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER_NAME}" \
    --workload-identity-pool="${WIF_POOL_NAME}" \
    --location="global" --format="value(name)" 2>/dev/null; then
  echo "WIF Provider '${WIF_PROVIDER_NAME}' already exists, skipping."
else
  gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER_NAME}" \
    --location="global" \
    --workload-identity-pool="${WIF_POOL_NAME}" \
    --display-name="GitHub Provider" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository_owner == '${GITHUB_ORG}' && assertion.repository == '${GITHUB_ORG}/${GITHUB_REPO}'"
  echo "WIF Provider '${WIF_PROVIDER_NAME}' created."
fi

# ---------------------------------------------------------------------------
# 8. Bind Service Account to Workload Identity Pool
# ---------------------------------------------------------------------------
echo ""
echo "[8/8] Binding service account to WIF pool..."

# Get the project number
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")

gcloud iam service-accounts add-iam-policy-binding "${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL_NAME}/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}" \
  --quiet

echo ""
echo "============================================="
echo " ✅ Setup Complete!"
echo "============================================="
echo ""
echo "Add these as GitHub Actions Secrets in:"
echo "  https://github.com/${GITHUB_ORG}/${GITHUB_REPO}/settings/secrets/actions"
echo ""
echo "WIF_PROVIDER:"
echo "  projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL_NAME}/providers/${WIF_PROVIDER_NAME}"
echo ""
echo "WIF_SERVICE_ACCOUNT:"
echo "  ${SERVICE_ACCOUNT_EMAIL}"
echo ""
echo "Also add these secrets:"
echo "  AQUA_REGISTRY_USERNAME - Your Aqua registry username"
echo "  AQUA_REGISTRY_PASSWORD - Your Aqua registry password"
echo "  AQUA_SERVER            - Your Aqua Gateway address (e.g., aqua-gw.example.com:8443)"
echo "  AQUA_TOKEN             - Your Aqua Enforcer group token"
echo ""
echo "And this GitHub Variable:"
echo "  AQUA_ME_VERSION        - MicroEnforcer version tag (e.g., 2022.4.874)"
echo ""
