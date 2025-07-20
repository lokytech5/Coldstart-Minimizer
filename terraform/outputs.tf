output "sagemaker_endpoint_arn" {
  value = var.endpoint_arn
}

output "sagemaker_endpoint_name" {
  value = var.endpoint_name
}

output "api_endpoint" {
  value = aws_api_gateway_deployment.api_deployment.invoke_url
}
