import boto3
import botocore
from twitter.models import Status

def get_twitter_post_processing_table():
    """
    Get the twitter processing table
    :return:
    """
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
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


def get_game_state_table():
    """
    Get the game state table
    :return:
    """
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    test_table_name = 'sam-quest-game-state'

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
                'AttributeName': 'TweetStartId',
                'KeyType': 'HASH'  # Partition key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'TweetStartId',
                'AttributeType': 'N'
            },
            {
                'AttributeName': 'GameCreator',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'CurrentTweetId',
                'AttributeType': 'N'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        },
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'GameCreator-index',
                'KeySchema': [
                    {
                        'AttributeName': 'GameCreator',
                        'KeyType': 'HASH'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 10,
                    'WriteCapacityUnits': 10
                }
            },
            {
                'IndexName': 'CurrentTweetId-index',
                'KeySchema': [
                    {
                        'AttributeName': 'CurrentTweetId',
                        'KeyType': 'HASH'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 10,
                    'WriteCapacityUnits': 10
                }
            }
        ]
    )

    return table

class MockTwitterApi():

    def __init__(self):
        self.mentions = []

    def SetMentions(self, mentions):
        self.mentions = mentions

    def GetMentions(self, since_id):
        return self.mentions

    def PostUpdate(self, status, in_reply_to_status_id=None):
        if len(status) > 140:
            raise ('Too many characters!')

        return Status.NewFromJsonDict({'id': 100})
