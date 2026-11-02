# Vayba landing zone on Google Cloud.
# Declares the bucket where source files land before Snowflake loads them,
# and who may read or write it. Real values live in terraform.tfvars (not committed).

terraform {
  required_version = ">= 1.9.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0" # pinned major version: same results on every machine
    }
  }

  # Remote state: shared by the team, versioned and locked by GCS.
  # This bucket is created once by hand (it must exist before Terraform can use it).
  backend "gcs" {
    bucket = "vayba-elimane-2026-tfstate"
    prefix = "vayba"
  }
}

# ---------- Inputs ----------

variable "project_id" {
  description = "GCP project that owns every resource"
  type        = string
}

variable "region" {
  description = "Where data is stored"
  type        = string
  default     = "europe-west9" # Paris, same city as the Snowflake account (AWS eu-west-3)
}

variable "uploaders" {
  description = "Members who upload source files, e.g. user:name@example.com"
  type        = list(string)
  default     = []
}

variable "readers" {
  description = "Members who only read the landing files"
  type        = list(string)
  default     = []
}

variable "snowflake_service_account" {
  description = "STORAGE_GCP_SERVICE_ACCOUNT from DESC STORAGE INTEGRATION; empty until it exists"
  type        = string
  default     = ""
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------- Storage ----------

# Landing bucket: ingestion scripts write here, Snowflake reads from here.
resource "google_storage_bucket" "landing" {
  name                        = "${var.project_id}-landing" # bucket names are global, so prefix with the project
  location                    = var.region
  uniform_bucket_level_access = true       # permissions on the whole bucket, never per file
  public_access_prevention    = "enforced" # can never be made public by mistake
  force_destroy               = false      # Terraform refuses to delete it while it holds data

  # Raw files are deleted after 30 days: limits cost and how long personal data is kept.
  # Consequence: files older than 30 days cannot be reloaded.
  lifecycle_rule {
    condition { age = 30 }
    action { type = "Delete" }
  }
}

# ---------- Access (least privilege) ----------

# Uploaders (ingestion owner) can add files...
resource "google_storage_bucket_iam_member" "uploader_write" {
  for_each = toset(var.uploaders)
  bucket   = google_storage_bucket.landing.name
  role     = "roles/storage.objectCreator"
  member   = each.value
}

# ...and uploaders and readers can list and read them. Nobody here can delete files.
resource "google_storage_bucket_iam_member" "uploader_read" {
  for_each = toset(concat(var.uploaders, var.readers))
  bucket   = google_storage_bucket.landing.name
  role     = "roles/storage.objectViewer"
  member   = each.value
}

# Custom read-only role with exactly the permissions Snowflake documents for loading.
# Built-in roles would grant more than COPY INTO needs.
resource "google_project_iam_custom_role" "snowflake_reader" {
  role_id     = "vaybaSnowflakeReader"
  title       = "Snowflake landing reader"
  permissions = ["storage.buckets.get", "storage.objects.get", "storage.objects.list"]
}

# Granted to Snowflake's service account only once it is known (count = 0 until then).
resource "google_storage_bucket_iam_member" "snowflake_read" {
  count  = var.snowflake_service_account == "" ? 0 : 1
  bucket = google_storage_bucket.landing.name
  role   = google_project_iam_custom_role.snowflake_reader.name
  member = "serviceAccount:${var.snowflake_service_account}"
}

# ---------- Outputs ----------

output "landing_bucket" {
  description = "Bucket URL to give to the ingestion scripts and the Snowflake stage"
  value       = google_storage_bucket.landing.url
}