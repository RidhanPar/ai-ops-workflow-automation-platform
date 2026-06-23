output "cloud_run_url" {
  description = "Public URL of the deployed Cloud Run backend service."
  value       = google_cloud_run_v2_service.backend.uri
}

output "artifact_registry_repo" {
  description = "Artifact Registry repository URI. Use this as the image prefix in Cloud Build."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.backend.repository_id}"
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name (PROJECT:REGION:INSTANCE). Used in DATABASE_URL and Cloud Build --add-cloudsql-instances."
  value       = google_sql_database_instance.main.connection_name
}

output "cloud_sql_instance_name" {
  description = "Cloud SQL instance resource name."
  value       = google_sql_database_instance.main.name
}

output "cloud_sql_public_ip" {
  description = "Cloud SQL instance public IP. Not used directly; connections go through the Auth Proxy."
  value       = google_sql_database_instance.main.public_ip_address
}

output "cloud_run_service_account" {
  description = "Service account email used by the Cloud Run service."
  value       = google_service_account.cloud_run.email
}

output "database_url_secret" {
  description = "Secret Manager secret ID holding the Cloud SQL DATABASE_URL."
  value       = google_secret_manager_secret.database_url.secret_id
}

output "deploy_command" {
  description = "Example gcloud command to trigger a manual Cloud Run deployment."
  value = join(" ", [
    "gcloud run deploy ${var.service_name}",
    "--image ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.backend.repository_id}/backend:latest",
    "--region ${var.region}",
    "--platform managed",
    "--project ${var.project_id}",
  ])
}
