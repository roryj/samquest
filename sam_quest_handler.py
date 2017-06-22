import base64
import json
import os
import twitter

import boto3
from time import sleep

from src.sam_quest import handle_game_state

# Constants
AWS_REGION = 'AWS_REGION'

total_processed = 0

# Environment Variables
aws_region = os.environ.get(AWS_REGION, 'us-west-2')
dynamodb_table_name = os.environ.get('TABLE_NAME', 'test-twitter-table')

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


def lambda_handler(event, context):
    # global dynamodb_table
    global total_processed

    posts = [json.loads(base64.b64decode(record['kinesis']['data'])) for record in event['Records']]

    # To avoid twitter throttling/locking, sleep 10 seconds after 10 records have been processed
    if total_processed >= 10:
        sleep(10)
        total_processed = 0

    handle_game_state(posts, twitter_api, dynamodb_table)
    total_processed += len(posts)
