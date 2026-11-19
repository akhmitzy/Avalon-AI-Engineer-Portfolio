output "api_internal_url" {
  value = "https://${aws_lb.api.dns_name}"
}

output "ecr_api_repository" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_worker_repository" {
  value = aws_ecr_repository.worker.repository_url
}

output "kms_key_arn" {
  value = aws_kms_key.main.arn
}

output "api_key_secret_arn" {
  description = "Set the value out of band: aws secretsmanager put-secret-value --secret-id <arn> --secret-string <key>"
  value       = aws_secretsmanager_secret.api_key.arn
}
