output "instance_public_ip" {
  description = "Public IP of the kai-planner VM — point your DNS A record here"
  value       = oci_core_instance.kai_planner.public_ip
}

output "instance_id" {
  description = "OCID of the compute instance"
  value       = oci_core_instance.kai_planner.id
}

output "vcn_id" {
  description = "OCID of the VCN"
  value       = oci_core_vcn.main.id
}

output "subnet_id" {
  description = "OCID of the public subnet"
  value       = oci_core_subnet.public.id
}

output "ssh_command" {
  description = "Copy-paste SSH command including identity file"
  value       = "ssh -i ${replace(var.ssh_public_key_path, ".pub", "")} -p ${var.ssh_port} ubuntu@${oci_core_instance.kai_planner.public_ip}"
}

output "dns_a_record" {
  description = "Value to set as the DNS A record for your domain"
  value       = oci_core_instance.kai_planner.public_ip
}
