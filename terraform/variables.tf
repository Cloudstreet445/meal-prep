variable "tenancy_ocid" {
  description = "OCID of your OCI tenancy"
  type        = string
}

variable "user_ocid" {
  description = "OCID of the OCI user running Terraform"
  type        = string
}

variable "fingerprint" {
  description = "Fingerprint of the API signing key"
  type        = string
}

variable "private_key_path" {
  description = "Path to the OCI API signing private key (.pem)"
  type        = string
}

variable "region" {
  description = "OCI region (e.g. ap-sydney-1)"
  type        = string
  default     = "ap-sydney-1"
}

variable "compartment_ocid" {
  description = "Compartment where all resources will be created. Defaults to root (tenancy) — correct for free accounts."
  type        = string
  default     = ""
}

locals {
  compartment_ocid = var.compartment_ocid != "" ? var.compartment_ocid : var.tenancy_ocid
}

variable "domain" {
  description = "Domain name for the application (e.g. kai-planner.cc)"
  type        = string
  default     = "kai-planner.cc"
}

variable "admin_email" {
  description = "Admin email for Let's Encrypt and fail2ban alerts"
  type        = string
  default     = "hackenbergblake@gmail.com"
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key added to the VM"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "ssh_port" {
  description = "Custom SSH port configured in shell.sh"
  type        = number
  default     = 2222
}

variable "instance_shape" {
  description = "Compute shape — VM.Standard.A1.Flex is OCI Always Free ARM"
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  description = "OCPUs for Flex shape (Always Free: up to 4 total across all A1 instances)"
  type        = number
  default     = 2
}

variable "instance_memory_gb" {
  description = "Memory in GB for Flex shape (Always Free: up to 24 GB)"
  type        = number
  default     = 12
}

variable "boot_volume_size_gb" {
  description = "Boot volume size in GB (Always Free: up to 200 GB total)"
  type        = number
  default     = 50
}
