# M4A転写システム - Google Cloud Platform Terraform設定
# Google Cloud E2インスタンス構成

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# プロバイダー設定
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# 変数定義
variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Google Cloud Region"
  type        = string
  default     = "asia-northeast1"
}

variable "zone" {
  description = "Google Cloud Zone"
  type        = string
  default     = "asia-northeast1-a"
}

variable "environment" {
  description = "環境名（development, staging, production）"
  type        = string
  default     = "production"
}

# ローカル変数
locals {
  app_name = "m4a-transcribe"
  labels = {
    application = local.app_name
    environment = var.environment
    managed-by  = "terraform"
  }
}

# ========================================
# ネットワーク構成
# ========================================

# カスタムVPCネットワーク
resource "google_compute_network" "main" {
  name                    = "${local.app_name}-network"
  auto_create_subnetworks = false
}

# サブネット
resource "google_compute_subnetwork" "main" {
  name          = "${local.app_name}-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.main.id

  # セカンダリ範囲（将来の拡張用）
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }
}

# ファイアウォールルール - HTTP/HTTPS
resource "google_compute_firewall" "allow_http_https" {
  name    = "${local.app_name}-allow-http-https"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "8000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["http-server", "https-server"]
}

# ファイアウォールルール - SSH
resource "google_compute_firewall" "allow_ssh" {
  name    = "${local.app_name}-allow-ssh"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["ssh-access"]
}

# ファイアウォールルール - ヘルスチェック
resource "google_compute_firewall" "allow_health_check" {
  name    = "${local.app_name}-allow-health-check"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }

  # Google Cloud Load Balancerのソース範囲
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = ["health-check"]
}

# ========================================
# ストレージ
# ========================================

# データ用Cloud Storage バケット
resource "google_storage_bucket" "app_data" {
  name          = "${var.project_id}-${local.app_name}-data"
  location      = var.region
  force_destroy = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  labels = local.labels
}

# バックアップ用Cloud Storage バケット
resource "google_storage_bucket" "backups" {
  name          = "${var.project_id}-${local.app_name}-backups"
  location      = var.region
  force_destroy = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }

  labels = local.labels
}

# ========================================
# Compute Engine 構成
# ========================================

# インスタンステンプレート
resource "google_compute_instance_template" "main" {
  name_prefix  = "${local.app_name}-template-"
  machine_type = "e2-standard-2"  # 2 vCPU, 8GB RAM
  
  can_ip_forward = false

  tags = ["http-server", "https-server", "health-check", local.app_name]

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"  # Container-Optimized OS
      size  = 50  # GB
      type  = "pd-standard"
    }
  }

  network_interface {
    network    = google_compute_network.main.id
    subnetwork = google_compute_subnetwork.main.id

    access_config {
      # エフェメラル外部IP
    }
  }

  service_account {
    email = google_service_account.compute.email
    scopes = [
      "https://www.googleapis.com/auth/devstorage.read_only",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
      "https://www.googleapis.com/auth/servicecontrol",
      "https://www.googleapis.com/auth/service.management.readonly",
      "https://www.googleapis.com/auth/trace.append"
    ]
  }

  metadata = {
    # Container-Optimized OSの設定
    "gce-container-declaration" = yamlencode({
      spec = {
        containers = [{
          name  = local.app_name
          image = "gcr.io/${var.project_id}/${local.app_name}:latest"
          
          ports = [{
            containerPort = 8000
            hostPort      = 8000
          }]

          env = [
            {
              name  = "ENVIRONMENT"
              value = var.environment
            },
            {
              name  = "LOG_LEVEL"
              value = "INFO"
            },
            {
              name  = "WORKERS"
              value = "2"
            }
          ]

          volumeMounts = [
            {
              name      = "data-volume"
              mountPath = "/app/data"
            },
            {
              name      = "logs-volume"
              mountPath = "/app/logs"
            }
          ]
        }]

        volumes = [
          {
            name = "data-volume"
            hostPath = {
              path = "/opt/m4a-transcribe/data"
            }
          },
          {
            name = "logs-volume"
            hostPath = {
              path = "/opt/m4a-transcribe/logs"
            }
          }
        ]

        restartPolicy = "Always"
      }
    })

    # Stackdriverロギング設定
    "google-logging-enabled" = "true"
    "google-monitoring-enabled" = "true"

    # SSH公開鍵（必要に応じて）
    # "ssh-keys" = "username:${file("~/.ssh/id_rsa.pub")}"
  }

  labels = local.labels

  lifecycle {
    create_before_destroy = true
  }
}

# マネージドインスタンスグループ
resource "google_compute_instance_group_manager" "main" {
  name = "${local.app_name}-mig"
  zone = var.zone

  base_instance_name = local.app_name
  target_size        = 2  # 可用性のため2台構成

  version {
    instance_template = google_compute_instance_template.main.id
  }

  named_port {
    name = "http"
    port = 8000
  }

  # 自動修復設定
  auto_healing_policies {
    health_check      = google_compute_health_check.main.id
    initial_delay_sec = 120
  }

  # アップデート設定
  update_policy {
    type                           = "PROACTIVE"
    instance_redistribution_type   = "PROACTIVE"
    minimal_action                 = "REPLACE"
    most_disruptive_allowed_action = "REPLACE"
    max_surge_fixed                = 1
    max_unavailable_fixed          = 0
    replacement_method             = "SUBSTITUTE"
  }
}

# ========================================
# ロードバランサー構成
# ========================================

# ヘルスチェック
resource "google_compute_health_check" "main" {
  name = "${local.app_name}-health-check"

  timeout_sec        = 10
  check_interval_sec = 30
  healthy_threshold  = 2
  unhealthy_threshold = 3

  http_health_check {
    request_path = "/health"
    port         = "8000"
  }
}

# バックエンドサービス
resource "google_compute_backend_service" "main" {
  name        = "${local.app_name}-backend-service"
  protocol    = "HTTP"
  timeout_sec = 30

  health_checks = [google_compute_health_check.main.id]

  backend {
    group           = google_compute_instance_group_manager.main.instance_group
    balancing_mode  = "UTILIZATION"
    max_utilization = 0.8
    capacity_scaler = 1.0
  }

  # セッションアフィニティ（必要に応じて）
  session_affinity = "NONE"

  # Connection Draining
  connection_draining_timeout_sec = 30
}

# URLマップ
resource "google_compute_url_map" "main" {
  name            = "${local.app_name}-url-map"
  default_service = google_compute_backend_service.main.id

  # 静的コンテンツのキャッシュ設定
  host_rule {
    hosts        = ["*"]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = google_compute_backend_service.main.id

    # APIエンドポイントはキャッシュしない
    path_rule {
      paths   = ["/api/*"]
      service = google_compute_backend_service.main.id
    }

    # 静的ファイルは長期キャッシュ
    path_rule {
      paths   = ["/static/*"]
      service = google_compute_backend_service.main.id
    }
  }
}

# HTTPSプロキシ
resource "google_compute_target_https_proxy" "main" {
  name             = "${local.app_name}-https-proxy"
  url_map          = google_compute_url_map.main.id
  ssl_certificates = [google_compute_managed_ssl_certificate.main.id]
}

# HTTPプロキシ（HTTPS リダイレクト用）
resource "google_compute_target_http_proxy" "main" {
  name    = "${local.app_name}-http-proxy"
  url_map = google_compute_url_map.redirect.id
}

# HTTPS リダイレクト用URLマップ
resource "google_compute_url_map" "redirect" {
  name = "${local.app_name}-redirect-url-map"

  default_url_redirect {
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    https_redirect         = true
    strip_query            = false
  }
}

# SSL証明書（マネージド）
resource "google_compute_managed_ssl_certificate" "main" {
  name = "${local.app_name}-ssl-cert"

  managed {
    domains = ["m4a-transcribe.example.com"]  # 実際のドメインに変更
  }

  lifecycle {
    create_before_destroy = true
  }
}

# グローバル転送ルール（HTTPS）
resource "google_compute_global_forwarding_rule" "https" {
  name       = "${local.app_name}-https-forwarding-rule"
  target     = google_compute_target_https_proxy.main.id
  port_range = "443"
  ip_address = google_compute_global_address.main.id
}

# グローバル転送ルール（HTTP - リダイレクト用）
resource "google_compute_global_forwarding_rule" "http" {
  name       = "${local.app_name}-http-forwarding-rule"
  target     = google_compute_target_http_proxy.main.id
  port_range = "80"
  ip_address = google_compute_global_address.main.id
}

# グローバルIPアドレス
resource "google_compute_global_address" "main" {
  name = "${local.app_name}-global-ip"
}

# ========================================
# IAM とサービスアカウント
# ========================================

# Compute Engine用サービスアカウント
resource "google_service_account" "compute" {
  account_id   = "${local.app_name}-compute"
  display_name = "M4A Transcribe Compute Engine Service Account"
}

# Cloud Storage アクセス権限
resource "google_storage_bucket_iam_member" "compute_data_access" {
  bucket = google_storage_bucket.app_data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.compute.email}"
}

# Cloud Storage バックアップアクセス権限
resource "google_storage_bucket_iam_member" "compute_backup_access" {
  bucket = google_storage_bucket.backups.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.compute.email}"
}

# ========================================
# 出力値
# ========================================

output "load_balancer_ip" {
  description = "Load Balancer IP Address"
  value       = google_compute_global_address.main.address
}

output "instance_group_manager" {
  description = "Managed Instance Group Name"
  value       = google_compute_instance_group_manager.main.name
}

output "storage_bucket_data" {
  description = "Data Storage Bucket Name"
  value       = google_storage_bucket.app_data.name
}

output "storage_bucket_backups" {
  description = "Backups Storage Bucket Name"
  value       = google_storage_bucket.backups.name
}