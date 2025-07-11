import boto3
import time
import pandas as pd
import json
import os

region = "us-east-1"
sagemaker = boto3.client("sagemaker", region_name=region)
s3 = boto3.client("s3", region_name=region)

bucket = "sagemaker-us-east-1-061039798341"
json_data_prefix = "deepar-json/"
train_data_uri = f"s3://{bucket}/{json_data_prefix}"
output_uri = f"s3://{bucket}/output/"
training_job_name = f"deepar-training-{int(time.time())}"
model_name = f"deepar-model-{int(time.time())}"
role_arn = "arn:aws:iam::061039798341:role/service-role/AmazonSageMaker-ExecutionRole-20250704T082477"
training_image = "522234722520.dkr.ecr.us-east-1.amazonaws.com/forecasting-deepar:latest"


def convert_csv_to_deepar_json(csv_key, json_key):
    """Download CSV from S3, convert to DeepAR JSON format, and upload back to S3."""
    tmp_csv = "/tmp/train.csv"
    tmp_json = "/tmp/train.json"

    # Download CSV file
    s3.download_file(bucket, csv_key, tmp_csv)
    print(f"Downloaded {csv_key} from S3.")

    # Read CSV and convert
    df = pd.read_csv(tmp_csv)
    time_col = 'minute'
    target_col = 'invocation_count'

    # Check columns exist
    if time_col not in df.columns or target_col not in df.columns:
        raise ValueError(
            f"CSV must contain '{time_col}' and '{target_col}' columns. Got {list(df.columns)}")

    # Remove timezone from the start string
    start_value = df[time_col].iloc[0]
    if isinstance(start_value, str):
        start_value = start_value.split("+")[0].split("Z")[0].strip()
    else:
        start_value = pd.Timestamp(start_value).tz_localize(
            None).strftime("%Y-%m-%d %H:%M:%S")

    entry = {
        "start": start_value,
        "target": df[target_col].tolist()
    }

    # Write JSON Lines to local file
    with open(tmp_json, "w") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"Converted to DeepAR JSON at {tmp_json}")

    # Upload to S3 in the deepar-json/ folder
    s3.upload_file(tmp_json, bucket, json_key)
    print(f"Uploaded DeepAR JSON to s3://{bucket}/{json_key}")


def check_and_prepare_training_data():
    # List objects in the training prefix
    train_csv_prefix = "training/"
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=train_csv_prefix)
    has_json = False

    for obj in resp.get("Contents", []):
        key = obj["Key"]
        if key.endswith(".csv"):
            # Write JSON output to deepar-json/ instead of training/
            json_filename = os.path.basename(key).rsplit(".", 1)[0] + ".json"
            json_key = f"{json_data_prefix}{json_filename}"
            print(f"Converting {key} to {json_key} ...")
            convert_csv_to_deepar_json(key, json_key)
            has_json = True

    if not has_json:
        raise Exception(
            f"No CSV file found in s3://{bucket}/{train_csv_prefix} to convert to DeepAR JSON.")


# 0. Check for CSV in 'training/', convert to DeepAR JSON in 'deepar-json/'
check_and_prepare_training_data()

# 1. Start training (input points to deepar-json/)
sagemaker.create_training_job(
    TrainingJobName=training_job_name,
    AlgorithmSpecification={
        "TrainingImage": training_image,
        "TrainingInputMode": "File"
    },
    RoleArn=role_arn,
    InputDataConfig=[
        {
            "ChannelName": "train",
            "DataSource": {
                "S3DataSource": {
                    "S3DataType": "S3Prefix",
                    "S3Uri": train_data_uri,
                    "S3DataDistributionType": "FullyReplicated"
                }
            },
            "ContentType": "json"
        }
    ],
    OutputDataConfig={
        "S3OutputPath": output_uri
    },
    ResourceConfig={
        "InstanceType": "ml.m5.xlarge",
        "InstanceCount": 1,
        "VolumeSizeInGB": 10
    },
    HyperParameters={
        "time_freq": "min",
        "context_length": "60",
        "prediction_length": "10",
        "num_cells": "50",
        "epochs": "100"
    },
    StoppingCondition={
        "MaxRuntimeInSeconds": 3600
    }
)

print(f"Started training job: {training_job_name}")

# 2. Wait for completion
print("Waiting for training to complete...")
while True:
    status = sagemaker.describe_training_job(TrainingJobName=training_job_name)[
        "TrainingJobStatus"]
    print("Current status:", status)
    if status in ["Completed", "Failed", "Stopped"]:
        break
    time.sleep(60)

if status != "Completed":
    raise Exception(f"Training did not complete successfully: {status}")

# 3. Register new model with output artifact
artifact_path = sagemaker.describe_training_job(TrainingJobName=training_job_name)[
    "ModelArtifacts"]["S3ModelArtifacts"]

print(f"Model artifact is at: {artifact_path}")

sagemaker.create_model(
    ModelName=model_name,
    PrimaryContainer={
        "Image": training_image,
        "ModelDataUrl": artifact_path
    },
    ExecutionRoleArn=role_arn
)

print(f"Registered new SageMaker model: {model_name}")
print(f"Update your Terraform variable 'model_data_url' to: {artifact_path}")
print("Then run: terraform apply")
