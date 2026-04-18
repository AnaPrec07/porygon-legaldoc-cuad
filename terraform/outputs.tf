output "cloud_run_url" {
  value = google_cloud_run_v2_service.mcp_server.uri
}

output "artifact_registry_repo" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}"
}

output "cicd_sa_email" {
  value = google_service_account.cicd_sa.email
}