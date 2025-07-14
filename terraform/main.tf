provider "aws" {
  region = "us-east-1"
}

terraform {
  backend "s3" {
    bucket         = "coldstartminimizer-state"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "coldStartMinizer-Lock"
  }
}

variable "bucket_name" {
  type    = string
  default = "sagemaker-us-east-1-061039798341"
}

variable "endpoint_name" {
  type    = string
  default = "deepar-ecommerce-endpoint"
}

variable "endpoint_arn" {
  type    = string
  default = "arn:aws:sagemaker:us-east-1:061039798341:endpoint/deepar-ecommerce-endpoint"
}

variable "threshold" {
  type    = number
  default = 130
}

variable "model_data_url" {
  description = "S3 URI for the trained SageMaker model artifact"
  type        = string
}


#Fecthing neccessary role premission from AWS IAM
data "aws_iam_role" "Coldstart_Lambda_Role" {
  name = "ColdStartLambdaRole"
}

data "aws_iam_role" "Coldstart_Sagemaker_Role" {
  name = "ColdStartSageMakerRole"
}

data "aws_iam_role" "Coldstart_StepFunction_Role" {
  name = "ColdStartStepFunctionRole"
}

# Target Function
resource "aws_lambda_function" "target_function" {
  function_name    = "target_function"
  handler          = "target_function.lambda_handler"
  runtime          = "python3.13"
  role             = data.aws_iam_role.Coldstart_Lambda_Role.arn
  filename         = "${path.module}/../src/lambda/target_function.zip"
  source_code_hash = filebase64sha256("${path.module}/../src/lambda/target_function.zip")
  memory_size      = 256
  timeout          = 30
}

#Lamba Function: init_manager
resource "aws_lambda_function" "init_manager" {
  function_name    = "init_manager"
  role             = data.aws_iam_role.Coldstart_Lambda_Role.arn
  handler          = "init_manager.lambda_handler"
  runtime          = "python3.13"
  architectures    = ["x86_64"]
  source_code_hash = filebase64sha256("${path.module}/../src/lambda/init_manager.zip")
  filename         = "${path.module}/../src/lambda/init_manager.zip"
  environment {
    variables = {
      BUCKET_NAME     = var.bucket_name
      ENDPOINT_NAME   = var.endpoint_name
      THRESHOLD       = tostring(var.threshold)
      TARGET_FUNCTION = "target_function" # Name of the target function to invoke
    }
  }
}

#cloudwatch(EventBridge) Rule for init_manager
resource "aws_cloudwatch_event_rule" "every_one_minute" {
  name                = "every-one-minute"
  schedule_expression = "rate(1 minute)"
}

resource "aws_cloudwatch_event_target" "check_cold_start" {
  rule      = aws_cloudwatch_event_rule.every_one_minute.name
  target_id = "init_manager"
  arn       = aws_lambda_function.init_manager.arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.init_manager.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.every_one_minute.arn
}

#Lambda Function: data Collector
resource "aws_lambda_function" "data_collector" {
  function_name    = "data_collector"
  handler          = "data_collector.lambda_handler"
  runtime          = "python3.13"
  role             = data.aws_iam_role.Coldstart_Lambda_Role.arn
  filename         = "${path.module}/../src/lambda/data_collector.zip"
  source_code_hash = filebase64sha256("${path.module}/../src/lambda/data_collector.zip")
  timeout          = 30
}

resource "aws_cloudwatch_event_rule" "collect_metrics_target" {
  name                = "collect_metrics"
  schedule_expression = "rate(5 minutes)"
  depends_on          = [aws_lambda_function.data_collector]
}

resource "aws_cloudwatch_event_target" "collect_metrics_target" {
  rule      = aws_cloudwatch_event_rule.collect_metrics_target.name
  target_id = "data_collector"
  arn       = aws_lambda_function.data_collector.arn
}

#Premission Code here

resource "aws_lambda_permission" "allow_cloudwatch_data" {
  statement_id  = "AllowExecutionFromCloudWatchData"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.collect_metrics_target.arn
}


#Step functions State Machine
resource "aws_sfn_state_machine" "jit_workflow" {
  name     = "ecommerce_jit_workflow"
  role_arn = data.aws_iam_role.Coldstart_StepFunction_Role.arn
  definition = jsonencode({
    Comment = "Workflow to handle JIT Lambda initialization",
    StartAt = "CheckForecast",
    States = {
      CheckForecast = {
        Type       = "Task",
        Resource   = "arn:aws:states:::lambda:invoke",
        Parameters = { "Payload" : { "Input" : { "action" : "check" } }, "FunctionName" : aws_lambda_function.init_manager.arn },
        Next       = "Decision"
      },
      Decision = {
        Type    = "Choice",
        Choices = [{ "Variable" : "$.Payload.forecast", "NumericGreaterThanEquals" : "${var.threshold}", "Next" : "InitializeJIT" }],
        Default = "NoAction"
      },
      InitializeJIT = {
        Type       = "Task",
        Resource   = "arn:aws:states:::lambda:invoke",
        Parameters = { "Payload" : { "Input" : { "action" : "init" } }, "FunctionName" : aws_lambda_function.init_manager.arn },
        End        = true
      },
      NoAction = { Type = "Succeed" }
    }
  })
}

# SageMaker Model
resource "aws_sagemaker_model" "deepar_model" {
  name               = "${var.endpoint_name}-model"
  execution_role_arn = data.aws_iam_role.Coldstart_Sagemaker_Role.arn
  primary_container {
    image          = "522234722520.dkr.ecr.us-east-1.amazonaws.com/forecasting-deepar:latest"
    model_data_url = var.model_data_url
  }
}


# SageMaker Endpoint Configuration
resource "aws_sagemaker_endpoint_configuration" "deepar_endpoint_config" {
  name = "${var.endpoint_name}-config"
  production_variants {
    variant_name           = "default"
    model_name             = aws_sagemaker_model.deepar_model.name
    initial_instance_count = 1
    instance_type          = "ml.m5.large"
  }
  depends_on = [aws_sagemaker_model.deepar_model]
}
