import pandas as pd
import time
import boto3

transcribe = boto3.client("transcribe", 
aws_access_key_id = "AKIA4HK6S6KQYY2M4TOH", 
aws_secret_access_key = "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", 
region_name = "us-east-2")

print(transcribe)
