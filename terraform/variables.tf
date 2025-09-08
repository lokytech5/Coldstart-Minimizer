variable "region" {
  description = "AWS region"
  default     = "us-east-1"
}

variable "demo_orders_lambda_name" {
  description = "Name of the demo Lambda to optionally prewarm (e.g., demo-orders-api). Leave empty to disable."
  type        = string
  default     = ""
}
