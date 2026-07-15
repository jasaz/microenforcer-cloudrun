# Cloud Run with Aqua MicroEnforcer — CI/CD Pipeline

Deploy a Flask Hello World application to **Google Cloud Run** with **Aqua MicroEnforcer** runtime protection, using **GitHub Actions** and **Workload Identity Federation** (keyless authentication).

## Prerequisites

- **GCP Project**: `your_projectname` (must already exist)
- **Aqua Security account** with access to `Aquasec Registry`
- **GitHub repository**: [jasaz/microenforcer-cloudrun](https://github.com/jasaz/microenforcer-cloudrun)
- **gcloud CLI** installed and authenticated with Owner/Editor permissions

## Project Structure

```
microenforcer-cloudrun/
├── .github/
│   └── workflows/
│       └── deploy.yml            # GitHub Actions CI/CD pipeline
├── app/
│   ├── Dockerfile                # Flask app container image
│   ├── app.py                    # Hello World Flask application
│   └── requirements.txt          # Python dependencies
├── setup/
│   └── setup-wif.sh              # GCP WIF & infrastructure setup script
├── service.yaml                  # Cloud Run multi-container service definition
└── README.md                     # This file
```

## One-Time Setup

### 1. Run the GCP Setup Script

This creates the Artifact Registry repository, Service Account, Workload Identity Pool, and OIDC Provider:

```bash
chmod +x setup/setup-wif.sh
./setup/setup-wif.sh
```

The script will output the values you need for GitHub secrets.

### 2. Configure GitHub Secrets

Go to **Settings → Secrets and variables → Actions** in your GitHub repository and add:

| Secret Name | Description | Example |
|---|---|---|
| `WIF_PROVIDER` | Full WIF provider resource name | `projects/123456789/locations/global/workloadIdentityPools/github-wif-pool/providers/github-provider` |
| `WIF_SERVICE_ACCOUNT` | WIF service account | sa-name@project-id.iam.gserviceaccount.com |
| `WIF_SERVICE_ACCOUNT` | GCP service account email | `github-deployer@project_id.iam.gserviceaccount.com` |
| `AQUA_REGISTRY_USERNAME` | Aqua Docker registry username | `myuser@company.com` |
| `AQUA_REGISTRY_PASSWORD` | Aqua Docker registry password | `••••••••` |
| `AQUA_SERVER` | Aqua Gateway/Console address | `aqua-gateway.example.com:443` |
| `AQUA_TOKEN` | Aqua Enforcer group token | `••••••••` |

Please note that WIF_PROVIDER & WIF_SERVICE_ACCOUNT can be obtained after the execution of setup-wif.sh

### 3. Configure GitHub Variables

Go to **Settings → Secrets and variables → Actions → Variables** and add:

| Variable Name | Description | Example |
|---|---|---|
| `AQUA_DEBUG_LEVEL` | MicroEnforcer image version tag | `3` |
| `AQUA_DEBUG_TYPE` | MicroEnforcer image version tag | `STDOUT` |
| `AQUA_IMAGE_ID` | MicroEnforcer image version tag | `sha256:...` |
| `AQUA_ME_VERSION` | MicroEnforcer image version tag | `2022.4.880` |
| `AQUA_MICROENFORCER` | MicroEnforcer image version tag | `1` |

## CI/CD Pipeline

The pipeline triggers automatically on every push to `main`:

1. **Authenticate** to GCP using Workload Identity Federation (no keys/JSON)
2. **Mirror** the Aqua MicroEnforcer image from `registry.aquasec.com` to Artifact Registry using `crane copy`
3. **Build & push** the Flask app container image to Artifact Registry
4. **Deploy** the multi-container Cloud Run service using `gcloud run services replace`
5. **Route** all traffic to the latest revision