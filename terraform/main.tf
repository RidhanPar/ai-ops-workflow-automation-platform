terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6"
    }
  }

  # Uncomment and configure to store state in GCS instead of locally:
  # backend "gcs" {
  #   bucket = "YOUR_TERRAFORM_STATE_BUCKET"
  #   prefix = "aiops/terraform/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# GCP APIs
# ---------------------------------------------------------------------------

locals {
  required_apis = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)

  service            = each.key
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Artifact Registry
# ---------------------------------------------------------------------------

resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = "aiops-backend"
  format        = "DOCKER"
  description   = "AI Ops platform backend container images"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}

# ---------------------------------------------------------------------------
# Cloud SQL (PostgreSQL 16 with pgvector)
# ---------------------------------------------------------------------------

resource "random_password" "db_password" {
  length  = 32
  special = false # avoid shell-escaping issues in connection strings
}

resource "google_sql_database_instance" "main" {
  name             = var.db_instance_name
  database_version = "POSTGRES_16"
  region           = var.region

  deletion_protection = var.deletion_protection

  settings {
    tier              = var.db_tier
    availability_type = var.db_availability_type

    ip_configuration {
      # Public IP is required for the Cloud SQL Auth Proxy approach used by
      # Cloud Run. No authorized_networks are added; all access is via the
      # proxy, which authenticates using the service account.
      ipv4_enabled = true
    }

    backup_configuration {
      enabled    = var.db_availability_type == "REGIONAL"
      start_time = "03:00"
    }

    # Enable the pgvector extension so the Alembic migration can run
    # "CREATE EXTENSION IF NOT EXISTS vector" on startup.
    database_flags {
      name  = "cloudsql.enable_pgvector"
      value = "on"
    }
  }

  depends_on = [google_project_service.apis["sqladmin.googleapis.com"]]
}

resource "google_sql_database" "aiops" {
  name     = "aiops"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "aiops" {
  name     = "aiops"
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
}

# ---------------------------------------------------------------------------
# Secret Manager
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "database_url" {
  secret_id = "aiops-database-url"
  replication { auto {} }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id

  # Cloud SQL Auth Proxy mounts the socket at /cloudsql/<connection_name>.
  # psycopg2 connects to the socket via the ?host= query parameter.
  secret_data = join("", [
    "postgresql+psycopg2://",
    google_sql_user.aiops.name,
    ":",
    random_password.db_password.result,
    "@/",
    google_sql_database.aiops.name,
    "?host=/cloudsql/",
    google_sql_database_instance.main.connection_name,
  ])
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "aiops-db-password"
  replication { auto {} }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "aiops-jwt-secret"
  replication { auto {} }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "jwt_secret" {
  secret      = google_secret_manager_secret.jwt_secret.id
  secret_data = var.jwt_secret
}

resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "aiops-openai-api-key"
  replication { auto {} }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "openai_api_key" {
  secret      = google_secret_manager_secret.openai_api_key.id
  secret_data = var.openai_api_key
}

# ---------------------------------------------------------------------------
# Service account for Cloud Run
# ---------------------------------------------------------------------------

resource "google_service_account" "cloud_run" {
  account_id   = "aiops-cloud-run"
  display_name = "AI Ops Cloud Run service account"
}

resource "google_project_iam_member" "cloud_run_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_artifact_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# ---------------------------------------------------------------------------
# Cloud Run service
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "backend" {
  name     = var.service_name
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # Mount the Cloud SQL Auth Proxy socket directory.
    # Cloud Run injects the proxy automatically when cloud_sql_instance is set;
    # the socket appears at /cloudsql/<project>:<region>:<instance>.
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }

    containers {
      image = join("/", [
        "${var.region}-docker.pkg.dev/${var.project_id}",
        google_artifact_registry_repository.backend.repository_id,
        "backend:${var.image_tag}",
      ])

      # start_render.py: runs alembic migrations, optional demo seed, then
      # exec's uvicorn on $PORT. This replaces the Dockerfile default CMD.
      command = ["python", "start_render.py"]

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.container_cpu
          memory = var.container_memory
        }
        # Release CPU when request handling is idle (required for scale-to-zero).
        cpu_idle          = true
        startup_cpu_boost = true
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      # Plain environment variables
      env { name = "APP_ENV"; value = "production" }
      env { name = "PORT"; value = "8080" }
      env { name = "CORS_ORIGINS"; value = var.cors_origins }
      env { name = "DEMO_SEED_ENABLED"; value = tostring(var.demo_seed_enabled) }
      env { name = "LOG_LEVEL"; value = "INFO" }
      env { name = "OTEL_SERVICE_NAME"; value = "ai-ops-workflow-platform" }

      # Secrets injected from Secret Manager at container startup
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "JWT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "OPENAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.openai_api_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_iam_member.cloud_run_sql_client,
    google_project_iam_member.cloud_run_secret_accessor,
    google_sql_user.aiops,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_version.jwt_secret,
    google_secret_manager_secret_version.openai_api_key,
  ]
}

# Allow unauthenticated invocations. Application-level auth is handled by JWT.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  name     = google_cloud_run_v2_service.backend.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------------------------
# Cloud Build permissions
# Cloud Build's default service account needs to push images and deploy.
# ---------------------------------------------------------------------------

data "google_project" "project" {}

locals {
  cloudbuild_sa = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

resource "google_project_iam_member" "cloudbuild_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = local.cloudbuild_sa
}

resource "google_project_iam_member" "cloudbuild_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = local.cloudbuild_sa
}

# Required so Cloud Build can deploy the Cloud Run service as the Cloud Run
# service account (gcloud run deploy --service-account).
resource "google_project_iam_member" "cloudbuild_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = local.cloudbuild_sa
}
