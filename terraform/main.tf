provider "google" {
    project = "porygon-legaldoc-cuad"
    region = "us-central1"
}

resource "google_storage_bucket" "bucket" {
    name = "cuad-documents-porygon"
    location="us-central1"
    project = "porygon-legaldoc-cuad"
}

resource "google_kms_key_ring" "keyring" {
  name     = "dlp-keyring"
  location = "global"
  project  = "porygon-legaldoc-cuad"
}

resource "google_kms_crypto_key" "dlp_key" {
  name     = "dlp-key"
  key_ring = google_kms_key_ring.keyring.id
}

resource "google_project_service" "apis" {
  for_each = toset([
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudkms.googleapis.com",
    "dlp.googleapis.com",
    "documentai.googleapis.com",
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "dialogflow.googleapis.com"
  ])
  project            = "porygon-legaldoc-cuad"
  service            = each.value
  disable_on_destroy = false
}

# Service account
resource "google_service_account" "mcp_server_sa" {
  account_id   = "mcp-server-sa"
  display_name = "MCP Server Service Account"
  project      = var.project_id
}

# IAM bindings for the service account
resource "google_project_iam_member" "mcp_server_sa_roles" {
  for_each = toset([
    "roles/documentai.apiUser",
    "roles/storage.objectViewer",
    "roles/cloudkms.cryptoKeyEncrypterDecrypter",
    "roles/secretmanager.secretAccessor",
    "roles/artifactregistry.reader"
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.mcp_server_sa.email}"
}

# Create service account for CICD
resource "google_service_account" "cicd_sa" {
  account_id   = "cicd-deployer-sa"
  display_name = "CI/CD Deployer Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "cicd_sa_roles" {
  for_each = toset([
    "roles/artifactregistry.writer",   # push images
    "roles/run.developer",             # deploy Cloud Run revisions
    "roles/iam.serviceAccountUser",    # act as mcp-server-sa when deploying
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.cicd_sa.email}"
}

# Add artifact registry repository repository
resource "google_artifact_registry_repository" "mcp_server_repo" {
  location      = var.region
  repository_id = var.artifact_registry_repo
  format        = "DOCKER"
  project       = var.project_id
  description   = "Docker images for the Porygon MCP server"
  depends_on    = [google_project_service.apis]
}

# Create a cloud run instance
# Cloud Run v2 Service
resource "google_cloud_run_v2_service" "mcp_server" {
  name                = "porygon-mcp-server"
  location            = var.region
  project             = var.project_id

  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.mcp_server_sa.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}/mcp-server:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "REGION"
        value = var.region
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
  }
}

# Block unauthenticated access — callers must present a valid identity token
resource "google_cloud_run_v2_service_iam_member" "no_public_access" {
  project             = var.project_id
  location            = var.region
  name                = google_cloud_run_v2_service.mcp_server.name
  role                = "roles/run.invoker"
  member              = "serviceAccount:${google_service_account.mcp_server_sa.email}"
}