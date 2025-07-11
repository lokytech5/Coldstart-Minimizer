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
  role             = ""
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
  schedule_expression = "rate(1 mintue)"
}

#Check me out!!!!
resource "aws_cloudwatch_event_target" "check_cold_start" {
  rule      = ""
  target_id = "init_manager"
  arn       = ""
}

#Premission Code here



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
  schedule_expression = "rate(5 mintues)"
  depends_on          = [aws_lambda_function.data_collector]
}

resource "aws_cloudwatch_event_target" "collect_metrics_target" {
  rule      = ""
  target_id = "data_collector"
  arn       = ""
}

#Premission Code here


#Step functions State Machine
resource "aws_sfn_state_machine" "jit_workflow" {
  name     = "ecommerce_jit_workflow"
  role_arn = ""
  definition = jsondecode({
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
