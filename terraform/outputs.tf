output "sagemaker_endpoint_arn" {
  value = var.endpoint_arn
}

# Output for SageMaker Model Name
output "sagemaker_endpoint_name" {
  value = var.endpoint_name
}
output "api_endpoint" {
  value = "https://${aws_api_gateway_rest_api.ecommerce_api.id}.execute-api.${var.region}.amazonaws.com/${aws_api_gateway_stage.prod.stage_name}"
}

