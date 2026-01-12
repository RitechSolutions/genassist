output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "The ID of the public subnet"
  value       = aws_subnet.public.id
}

output "private_subnet_ids" {
  description = "The IDs of the private subnets"
  value       = [aws_subnet.private.id, aws_subnet.private_2.id]
}

output "database_endpoint" {
  description = "The connection endpoint for the RDS instance"
  value       = aws_db_instance.main.endpoint
}

output "database_name" {
  description = "The name of the database"
  value       = aws_db_instance.main.db_name
}

output "database_port" {
  description = "The port the database is listening on"
  value       = aws_db_instance.main.port
}

output "database_username" {
  description = "The master username for the database"
  value       = aws_db_instance.main.username
}

output "database_connection_string" {
  description = "The complete connection string for the database (password not included)"
  value       = "postgresql://${aws_db_instance.main.username}@${aws_db_instance.main.endpoint}:${aws_db_instance.main.port}/${aws_db_instance.main.db_name}"
  sensitive   = true
}

output "ecs_cluster_name" {
  description = "The name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "The ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "ecs_service_name" {
  description = "The name of the ECS service"
  value       = aws_ecs_service.app.name
}

output "ecr_repository_url" {
  description = "The URL of the ECR repository"
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_repository_name" {
  description = "The name of the ECR repository"
  value       = aws_ecr_repository.app.name
}

output "cloudwatch_log_group" {
  description = "The name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.app.name
}

output "security_group_db_id" {
  description = "The ID of the database security group"
  value       = aws_security_group.db.id
}

output "security_group_ecs_id" {
  description = "The ID of the ECS security group"
  value       = aws_security_group.ecs.id
} 