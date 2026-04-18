variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "porygon-legaldoc-cuad"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "force_destroy" {
  description = "Allow bucket deletion even if it contains objects"
  type        = bool
  default     = false
}

variable "artifact_registry_repo" {
  description = "Artifact Registry repository name"
  type        = string
  default     = "porygon-mcp-server"
}