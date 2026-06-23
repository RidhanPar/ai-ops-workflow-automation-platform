# Terraform - GCP Cloud Run + Cloud SQL deployment

Provisions the full GCP infrastructure for the AI Ops platform backend:
Cloud Run service, Cloud SQL PostgreSQL 16 instance with pgvector, Artifact
Registry Docker repository, Secret Manager secrets, and all required IAM
bindings.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) authenticated with an account that has Project Owner or a combination of Editor + Security Admin on the target project
- A GCP project with billing enabled
- Docker (only needed for local image builds; Cloud Build handles CI builds)

## Quickstart

```bash
cd terraform

# Authenticate
gcloud auth application-default login

# Create a terraform.tfvars file (never commit this file)
cat > terraform.tfvars <<EOF
project_id     = "your-gcp-project-id"
jwt_secret     = "at-least-32-random-chars-here"
openai_api_key = ""
cors_origins   = "https://your-frontend-url.example.com"
EOF

terraform init
terraform plan
terraform apply
```

`terraform apply` outputs the Cloud Run URL, Artifact Registry repo URI, and
the Cloud SQL connection name. The backend starts, runs Alembic migrations,
and serves the API automatically on first deployment.

## Variables

| Variable | Default | Description |
|---|---|---|
| `project_id` | required | GCP project ID |
| `region` | `us-central1` | GCP region for all resources |
| `db_instance_name` | `aiops-postgres` | Cloud SQL instance name |
| `db_tier` | `db-f1-micro` | Cloud SQL machine tier |
| `db_availability_type` | `ZONAL` | ZONAL or REGIONAL (HA) |
| `deletion_protection` | `false` | GCP-level Cloud SQL deletion lock |
| `service_name` | `aiops-backend` | Cloud Run service name |
| `image_tag` | `latest` | Image tag to deploy |
| `min_instances` | `0` | Scale-to-zero when idle |
| `max_instances` | `10` | Max concurrent instances |
| `container_cpu` | `1000m` | CPU limit per instance |
| `container_memory` | `512Mi` | Memory limit per instance |
| `jwt_secret` | required | JWT signing secret (stored in Secret Manager) |
| `openai_api_key` | `""` | OpenAI key (empty uses local fallback) |
| `cors_origins` | `https://example.com` | Comma-separated allowed origins |
| `demo_seed_enabled` | `false` | Seed demo data on first startup |

## Architecture

```
Cloud Build
  |-- builds backend/Dockerfile
  |-- pushes to Artifact Registry
  +-- deploys to Cloud Run

Cloud Run (aiops-backend)
  |-- service account: aiops-cloud-run
  |-- reads secrets from Secret Manager
  |   |-- aiops-database-url
  |   |-- aiops-jwt-secret
  |   +-- aiops-openai-api-key
  +-- connects to Cloud SQL via Auth Proxy socket (/cloudsql/...)

Cloud SQL (PostgreSQL 16)
  |-- pgvector extension enabled via database flag
  |-- database: aiops
  |-- user: aiops (password in Secret Manager)
  +-- access: Cloud SQL Auth Proxy only (no authorized networks)
```

## Cloud SQL connection

The backend connects to Cloud SQL via the Cloud SQL Auth Proxy, which Cloud
Run injects automatically when the service template includes a
`cloud_sql_instance` volume. The DATABASE_URL uses the Unix socket path:

```
postgresql+psycopg2://aiops:PASSWORD@/aiops?host=/cloudsql/PROJECT:REGION:INSTANCE
```

This URL is assembled by Terraform and stored in Secret Manager as
`aiops-database-url`. The Cloud Run container reads it at startup.

## Cloud Build CI

`cloudbuild.yaml` at the repo root defines the pipeline:

1. Build `backend/Dockerfile`, tagged with the commit `$SHORT_SHA` and `latest`
2. Push both tags to Artifact Registry
3. Deploy the SHA-tagged image to Cloud Run

The Cloud Build trigger should be connected to the `main` branch in the GCP
Console under Cloud Build > Triggers, or with:

```bash
gcloud builds triggers create github \
  --repo-owner=RidhanPar \
  --repo-name=ai-ops-workflow-automation-platform \
  --branch-pattern='^main$' \
  --build-config=cloudbuild.yaml \
  --region=us-central1
```

## Terraform state

By default state is stored locally in `terraform.tfstate`. For team use or CI,
uncomment the `backend "gcs"` block in `main.tf` and create the bucket first:

```bash
gsutil mb -l us-central1 gs://YOUR_PROJECT_ID-tfstate
gsutil versioning set on gs://YOUR_PROJECT_ID-tfstate
```

## Tearing down

```bash
terraform destroy
```

If `deletion_protection = true` was set on the Cloud SQL instance, you must
set it to `false` and apply once before destroy will succeed:

```bash
terraform apply -var="deletion_protection=false"
terraform destroy
```
