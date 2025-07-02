provider "aws" {
  region = "us-east-1"
}

#comment here
resource "aws_s3_bucket" "demo_bucket" {
  bucket        = "demo-bucket-${random_id.suffix.hex}"
  force_destroy = true

  tags = {
    Name        = "Demo Bucket"
    Environment = "dev"
  }
}

resource "random_id" "suffix" {
  byte_length = 4
}
