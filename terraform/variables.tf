variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "GCP region for all resources."
  type        = string
  default     = "us-central1"
}

# ---- Cloud SQL ----

variable "db_instance_name" {
  description = "Cloud SQL instance name. Must be unique within the project."
  type        = string
  default     = "aiops-postgres"
}

variable "db_tier" {
  description = "Cloud SQL machine tier. Use db-f1-micro for dev, db-g1-small or higher for production."
  type        = string
  default     = "db-f1-micro"
}

variable "db_availability_type" {
  description = "ZONAL for single-zone (cheaper), REGIONAL for high-availability failover."
  type        = string
  default     = "ZONAL"

  validation {
    condition     = contains(["ZONAL", "REGIONAL"], var.db_availability_type)
    error_message = "db_availability_type must be ZONAL or REGIONAL."
  }
}

variable "deletion_protection" {
  description = "Enable GCP-level deletion protection on the Cloud SQL instance."
  type        = bool
  default     = false
}

# ---- Cloud Run ----

variable "service_name" {
  description = "Name of the Cloud Run service."
  type        = string
  default     = "aiops-backend"
}

variable "image_tag" {
  description = "Docker image tag to deploy. Overridden by Cloud Build with the commit SHORT_SHA."
  type        = string
  default     = "latest"
}

variable "min_instances" {
  description = "Minimum number of Cloud Run instances (0 scales to zero when idle)."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances."
  type        = number
  default     = 10
}

variable "container_cpu" {
  description = "CPU limit for each Cloud Run container instance."
  type        = string
  default     = "1000m"
}

variable "container_memory" {
  description = "Memory limit for each Cloud Run container instance."
  type        = string
  default     = "512Mi"
}

# ---- Application secrets ----

variable "jwt_secret" {
  description = "JWT signing secret. Must be at least 32 characters. Stored in Secret Manager."
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key. Leave empty to use the local fallback assistant."
  type        = string
  sensitive   = true
  default     = ""
}

variable "cors_origins" {
  description = "Comma-separated list of allowed CORS origins (e.g. the Cloud Run frontend URL)."
  type        = string
  default     = "https://example.com"
}

variable "demo_seed_enabled" {
  description = "Whether to seed demo tickets and agents on first startup."
  type        = bool
  default     = false
}
