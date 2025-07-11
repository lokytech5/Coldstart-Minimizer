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

variable "threshold" {
  type    = number
  default = 130
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
      BUCKET_NAME   = var.bucket_name
      ENDPOINT_NAME = var.endpoint_name
      THRESHOLD     = tostring(var.threshold)
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
  runtime          = "pythion3.10"
  role             = ""
  filename         = "${path.module}/../src/lambda/data_collector.zip"
  source_code_hash = filebase64sha256("${path.module}/../src/lambda/data_collector.zip")
}

resource "aws_cloudwatch_event_rule" "collect_metrics_target" {
  name                = "collect_metrics"
  schedule_expression = "rate(5 minutes)"
  depends_on          = [aws_lambda_function.data_collector]
}

resource "aws_cloudwatch_event_target" "collect_metrics_target" {
  rule      = aws_cloudwatch_event_rule.collect_metrics.name
  target_id = "data_collector"
  arn       = aws_lambda_function.data_collector.arn
}

#Premission Code here

resource "aws_lambda_permission" "allow_cloudwatch_data" {
  statement_id  = "AllowExecutionFromCloudWatchData"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.collect_metrics.arn
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

# SageMaker Training Job
resource "aws_sagemaker_training_job" "deepar_training" {
  name     = "deepar-training-${formatdate("YYYYMMDDhhmmss", timestamp())}"
  role_arn = data.aws_iam_role.Coldstart_Sagemaker_Role.arn
  algorithm_specification {
    training_image      = "522234722520.dkr.ecr.us-east-1.amazonaws.com/forecasting-deepar:latest"
    training_input_mode = "File"
  }
  output_data_config {
    s3_output_path = "s3://${var.bucket_name}/output/"
  }
  resource_config {
    instance_count    = 1
    instance_type     = "ml.m5.large"
    volume_size_in_gb = 10
  }
  hyper_parameters = {
    "time_freq"         = "min"
    "context_length"    = "60"
    "prediction_length" = "10"
    "num_cells"         = "50"
    "epochs"            = "100"
  }
  input_data_config {
    channel_name = "train"
    data_source {
      s3_data_source {
        s3_data_type = "S3Prefix"
        s3_uri       = "s3://${var.bucket_name}/training/"
      }
    }
    content_type = "json"
  }
}

# SageMaker Model
resource "aws_sagemaker_model" "deepar_model" {
  name               = "${var.endpoint_name}-model"
  execution_role_arn = data.aws_iam_role.Coldstart_Sagemaker_Role.arn
  primary_container {
    image          = "522234722520.dkr.ecr.us-east-1.amazonaws.com/forecasting-deepar:latest"
    model_data_url = aws_sagemaker_training_job.deepar_training.output_data_config[0].s3_output_path
  }
  depends_on = [aws_sagemaker_training_job.deepar_training]
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
  depends_on = [aws_sagemaker_training_job.deepar_training]
}

# SageMaker Endpoint
resource "aws_sagemaker_endpoint" "deepar_endpoint" {
  name                 = var.endpoint_name
  endpoint_config_name = aws_sagemaker_endpoint_configuration.deepar_endpoint_config.name
  depends_on           = [aws_sagemaker_endpoint_configuration.deepar_endpoint_config]
}
