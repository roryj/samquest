from time import sleep

import twitter
import boto3
import botocore
import os
import json
from boto3.dynamodb.conditions import Key, Attr
from src.models import TwitterGameRequest, GameState, RequestType
from random import randint

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

# Clients
dynamodb_table = None
twitter_api = None
kinesis_client = None

def get_api_credentials():
    return {
        'consumer_key': os.getenv('CONSUMER_KEY'),
        'consumer_secret': os.getenv('CONSUMER_SECRET'),
        'access_token_key': os.getenv('ACCESS_TOKEN_KEY'),
        'access_token_secret': os.getenv('ACCESS_TOKEN_SECRET')
    }


def lambda_handler(event, context):
    global dynamodb_table
    global twitter_api
    global kinesis_client

    if dynamodb_table is None:
        print('Setting up dynamodb table connection.')
        dynamodb_table = boto3.resource('dynamodb', region_name=aws_region).Table(dynamodb_table_name)

    if twitter_api is None:
        print('Setting up twitter client.')
        twitter_api = twitter.Api(**get_api_credentials())

    if kinesis_client is None:
        print('Setting up kinesis client.')
        kinesis_client = boto3.client('kinesis', region_name=aws_region)

    process_twitter_feed(twitter_api, kinesis_client, kinesis_stream, dynamodb_table)


def process_twitter_feed(twitter_api, kinesis_client, kinesis_stream, dynamo_table):
    """
    Process the twitter feed. The path for doing this will be:

    Login with token -> Get last processed values for tweets ->
    Process new games -> Process answers -> Process delayed games

    All requests are put into kinesis to be processed by the handle game state function
    :param event: The Lambda event
    :param context: The Lambda invoke context
    :return:
    """

    # Get last processed tweet_id from dynamo
    result = dynamo_table.query(
        KeyConditionExpression=Key('TwitterAccount').eq('@SAMQuest9'),
        ScanIndexForward=False, Limit=1)

    if result['Count'] == 0:
        last_processed_tweet_id = None
    else:
        last_processed_tweet_id = int(result['Items'][0]['TwitterPostId'])
        print ('Last processed tweet id: ' + str(last_processed_tweet_id))

    last_post_id = None

    # For each post, divide it into categories:
    # 1) New Game
    # 2) Joining a game
    # 3) Voting on choice
    for post in twitter_api.GetMentions(since_id=last_processed_tweet_id, trim_user=True):
        print(str(post))

        user = twitter_api.GetUser(user_id=post.user.id)

        hashtags = [tag.text for tag in post.hashtags]

        print(hashtags)

        if 'Help' in hashtags:
            request_type = RequestType.HELP
        elif 'LetsPlay' in hashtags:
            request_type = RequestType.CREATE_GAME
        elif 'StartGame' in hashtags:
            request_type = RequestType.START_GAME
        elif 'JoinGame' in hashtags:
            request_type = RequestType.JOIN_GAME
        elif 'ChooseMe' in hashtags:
            request_type = RequestType.MAKE_SELECTION
        else:
            request_type = RequestType.UNKNOWN

        game_request = TwitterGameRequest.NewFromJsonDict({'user_name': user.screen_name,
                                                           'status_message': post.text,
                                                           'status_id': post.id,
                                                           'in_reply_to_status_id': post.in_reply_to_status_id,
                                                           'request_type': str(request_type),
                                                           'hashtags': hashtags})

        print('Sending to stream:')
        print(str(game_request))

        kinesis_client.put_record(StreamName=kinesis_stream,
                                  Data=str(game_request),
                                  PartitionKey='@SAMQuest9')

        last_post_id = post.id

    if last_post_id is not None:
        dynamo_table.put_item(Item={'TwitterAccount': '@SAMQuest9', 'TwitterPostId': last_post_id})

    print('Done processing twitters posts.')


def __get_local_dynamo_table():
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2', endpoint_url="http://localhost:8000")
    test_table_name = 'twitter-feed-test-table'

    try:
        table = dynamodb.Table(test_table_name)
        print (table.creation_date_time)
        return table
    except botocore.exceptions.ClientError as e:
        print('Table does not exist, creating table.')

    table = dynamodb.create_table(
        TableName= test_table_name,
        KeySchema=[
            {
                'AttributeName': 'TwitterAccount',
                'KeyType': 'HASH'  # Partition key
            },
            {
                'AttributeName': 'TwitterPostId',
                'KeyType': 'RANGE'  # Sort key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'TwitterAccount',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'TwitterPostId',
                'AttributeType': 'N'
            },

        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        }
    )

    return table

if __name__=='__main__':
    twitter_api = twitter.Api(**get_api_credentials())
    dynamodb_table = __get_local_dynamo_table()

    process_twitter_feed(twitter_api, None, None, dynamodb_table)

    result = dynamodb_table.scan()

    print('Result: ' + str(result))
