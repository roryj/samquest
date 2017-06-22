import twitter
import boto3
import os
from src.process_twitter_feed import process_twitter_feed

# Constants
ACCESS_TOKEN_KEY = 'ACCESS_TOKEN_KEY'
ACCESS_TOKEN_SECRET = 'ACCESS_TOKEN_SECRET'
CONSUMER_KEY = 'CONSUMER_KEY'
CONSUMER_SECRET = 'CONSUMER_SECRET'
AWS_REGION = 'AWS_REGION'

# Environment Variables
aws_region = os.environ.get(AWS_REGION, 'us-west-2')
dynamodb_table_name = os.environ.get('TABLE_NAME', 'test-twitter-table')
kinesis_stream = os.environ.get('KINESIS_STREAM', None)


def get_api_credentials():
    return {
        'consumer_key': os.getenv('CONSUMER_KEY'),
        'consumer_secret': os.getenv('CONSUMER_SECRET'),
        'access_token_key': os.getenv('ACCESS_TOKEN_KEY'),
        'access_token_secret': os.getenv('ACCESS_TOKEN_SECRET')
    }


# Clients
print('Setting up dynamodb table connection.')
dynamodb_table = boto3.resource('dynamodb', region_name=aws_region).Table(dynamodb_table_name)
print('Setting up twitter client.')
twitter_api = twitter.Api(**get_api_credentials())
print('Setting up kinesis client.')
kinesis_client = boto3.client('kinesis', region_name=aws_region)


def lambda_handler(event, context):
    process_twitter_feed(twitter_api, kinesis_client, kinesis_stream, dynamodb_table)

