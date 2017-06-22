import base64
import json
import os

import boto3
import botocore
import twitter
from boto3.dynamodb.conditions import Key, Attr
import string
import random
from time import sleep

from src.game_steps import get_choice, Choice
from src.models import TwitterGameRequest, RequestType, GameState, GameSession, MockTwitterApi

# Constants
ACCESS_TOKEN_KEY = 'ACCESS_TOKEN_KEY'
ACCESS_TOKEN_SECRET = 'ACCESS_TOKEN_SECRET'
CONSUMER_KEY = 'CONSUMER_KEY'
CONSUMER_SECRET = 'CONSUMER_SECRET'
AWS_REGION = 'AWS_REGION'

total_processed = 0

# Environment Variables
aws_region = os.environ.get(AWS_REGION, 'us-west-2')
dynamodb_table_name = os.environ.get('TABLE_NAME', 'test-twitter-table')

# Clients
dynamodb_table = None
twitter_api = None

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
    global total_processed

    if dynamodb_table is None:
        print('Setting up dynamodb table connection.')
        dynamodb_table = boto3.resource('dynamodb', region_name=aws_region).Table(dynamodb_table_name)

    if twitter_api is None:
        print('Setting up twitter client.')
        twitter_api = twitter.Api(**get_api_credentials())

    posts = [json.loads(base64.b64decode(record['kinesis']['data'])) for record in event['Records']]

    # To avoid twitter throttling/locking, sleep 10 seconds after 10 records have been processed
    if total_processed % 10 == 0:
        sleep(10)

    handle_game_state(posts, twitter_api, dynamodb_table)
    total_processed += len(posts)

def handle_game_state(posts, twitter_api, dynamodb_table):

    print('Received ' + str(len(posts)) + ' records')

    for post in posts:

        print('Processing record ' + str(post))
        game_request = TwitterGameRequest.NewFromJsonDict(post)

        if RequestType(game_request.request_type) == RequestType.HELP:
            print('Getting help')
            __send_help(game_request, twitter_api)
        elif RequestType(game_request.request_type) == RequestType.CREATE_GAME:
            print('Creating game')
            __create_game(game_request, dynamodb_table, twitter_api)
        elif RequestType(game_request.request_type) == RequestType.START_GAME:
            print('Starting game')
            __start_game(game_request, dynamodb_table, twitter_api)
        elif RequestType(game_request.request_type) == RequestType.JOIN_GAME:
            print('Joining game')
            __join_game(game_request, dynamodb_table, twitter_api)
        elif RequestType(game_request.request_type) == RequestType.MAKE_SELECTION:
            print('Making a selection in the game')
            __make_selection(game_request, dynamodb_table, twitter_api)
        else:
            print('Unknown game type.')
            __send_error_tweet(game_request, twitter_api)

    print('Done processing.')


def __send_help(game_request, twitter_api):
    """
    Send a helpful message
    :param game_request:
    :param twitter_api:
    :return:
    """
    status_message = "Help: " \
                     "Create a quest with #LetsPlay. " \
                     "Start with #StartGame. " \
                     "Join with #JoinGame. " \
                     "Choose with #ChooseMe and your #selection."

    __send_to_twitter(status_message, game_request.in_reply_to_status_id, twitter_api)
    # print('Posting \"' + status_message + '\"')
    # twitter_api.PostUpdate(status=status_message,
    #                        in_reply_to_status_id=game_request.status_id)

def __send_to_twitter(status_message, reply_status_id, twitter_api):
    try:
        print('Posting \"' + status_message + '\"')

        status_message += ' '
        status_message += ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(4))

        return twitter_api.PostUpdate(status=status_message,
                               in_reply_to_status_id=reply_status_id)
    except Exception as e:
        print('An error occured: ' + str(e))
        return False


def __create_game(game_request, dynamodb_table, twitter_api):
    """
    The create game method. The logic is as follows =>

    1) Check that the user has not started a game
    2) Reply with request for joiners
    3) Post with post id into dynamodb
    4) Add new game to dynamo

    :param game_request:
    :param dynamodb_table:
    :param twitter_api:
    :return:
    """
    user = game_request.user_name

    result = dynamodb_table.query(IndexName='GameCreator-index',
                                  Select='ALL_ATTRIBUTES',
                                  KeyConditionExpression=Key('GameCreator').eq(user))

    if result['Count'] > 0 and any([game for game in result['Items'] if game['GameState'] != str(GameState.GAME_COMPLETE)]):
        status_message = "Hello @{}! You already have a game started!".format(user)
        __send_to_twitter(status_message, game_request.status_id, twitter_api)
        # print('Posting \"' + status_message + '\" to user ' + str(user))
        # twitter_api.PostUpdate(status=status_message,
        #                        in_reply_to_status_id=game_request.status_id)
    else:
        status_message = "Welcome to SAMQuest @{}! To start reply with #StartGame. " \
                     "To join this game, reply to this with #JoinGame".format(user)

        start_post_status = __send_to_twitter(status_message, game_request.status_id, twitter_api)
        # print('Posting \"' + status_message + '\" to user ' + str(user))
        # start_post_status = twitter_api.PostUpdate(status=status_message,
        #                                 in_reply_to_status_id=game_request.status_id)

        if start_post_status != False:
            game_session = GameSession.NewFromJsonDict({
                'TweetStartId': int(start_post_status.id),
                'GameState': str(GameState.PENDING_GAME_START),
                'GameCreator': user,
                'Players': [user],
                'TwitterSteps': [int(game_request.status_id)]
            })

            print(game_session.AsDict())

            dynamodb_table.put_item(Item=game_session.AsDict())


def __start_game(game_request, dynamodb_table, twitter_api):
    """
    The start game method. The logic is as follows =>

    1) Check the reply id to see if it exists
    2) Check to see that it is the creator
    3) Mark game as started in dynamo
    4) Post back first choice

    :param game_request:
    :param dynamodb_table:
    :param twitter_api:
    :return:
    """
    user = game_request.user_name
    try:
        result = dynamodb_table.get_item(Key={'TweetStartId': game_request.in_reply_to_status_id})
    except Exception as e:
        print('An error occured :( ' + str(e))
        return

    if 'Item' not in result or result['Item'] is None:
        status_message = "You are trying to start a game that doesn't exist @{}!".format(user)
        __send_to_twitter(status_message, game_request.status_id, twitter_api)
        # print('Posting \"' + status_message + '\" to user ' + str(user))
        # twitter_api.PostUpdate(status=status_message,
        #                        in_reply_to_status_id=game_request.status_id)
    elif result['Item']['GameCreator'] != user:
        status_message = "@{} you cannot start someone elses game! Create your own with #LetsPlay".format(user)
        __send_to_twitter(status_message, game_request.status_id, twitter_api)
        # print('Posting \"' + status_message + '\" to user ' + str(user))
        # twitter_api.PostUpdate(status=status_message,
        #                        in_reply_to_status_id=game_request.status_id)
    else:
        game_session = GameSession.NewFromJsonDict(result['Item'])

        game_session.GameState = str(GameState.PENDING_GAME_INPUT)

        current_choice = get_choice(1)

        users = " ".join(["@{}".format(player) for player in game_session.Players])
        choices = " ".join(["#{}".format(option.key) for option in current_choice.options])

        status_message = "{} {} {}".format(users, current_choice.text, choices)

        start_post_status = __send_to_twitter(status_message, None, twitter_api)
        # start_post_status = twitter_api.PostUpdate(status=status_message)

        if start_post_status != False:
            game_session.TwitterSteps += [int(start_post_status.id)]
            game_session.CurrentTweetId = int(start_post_status.id)
            game_session.CurrentGameStep = current_choice.id

            print(game_session.AsDict())
            dynamodb_table.put_item(Item=game_session.AsDict())
        else:
            print('Failure')


def __join_game(game_request, dynamodb_table, twitter_api):
    """
    The join game method. The logic goes as follows =>

    1) Validate this is a started game waiting for users to join
    2) Validate current players count is < 4
    3) Add user name to set of user aliases
    4) Reply with tweet

    :param game_request:
    :param dynamodb_table:
    :param twitter_api
    :return:
    """
    # result = dynamodb_table.query(Select='ALL_ATTRIBUTES',
    #                               KeyConditionExpression=Key('TweetStartId').eq(game_request.status_id))
    try:
        result = dynamodb_table.get_item(Key={'TweetStartId': game_request.in_reply_to_status_id})
    except Exception as e:
        print('an error occured: ' + str(e))
        return

    if 'Item' not in result or result['Item'] is None or len(result['Item']) == 0:
        status_message = "Hello @{}! I can't seem to find the game to start.".format(game_request.user_name)

    else:
        game_session = GameSession.NewFromJsonDict(result['Item'])

        if len(game_session.Players) == 4:
            status_message = "Hello @{}. The game is full, but you can try starting your own game!".format(game_request.user_name)
        else:
            game_session.Players += [game_request.user_name]
            dynamodb_table.put_item(Item=game_session.AsDict())
            status_message = "Hello @{}. Welcome to the game. Prepare yourself :)".format(game_request.user_name)

    __send_to_twitter(status_message, game_request.status_id, twitter_api)
    # print('Posting \"' + status_message + '\" to user ' + str(game_request.user_name))
    # twitter_api.PostUpdate(status=status_message,
    #                        in_reply_to_status_id=game_request.status_id)



def __make_selection(game_request, dynamodb_table, twitter_api):
    """
    Handle tweets that are game related. The three scenarios here are:

    1) The game does not exist
    2) The game exists, and you are not part of it
    3) The game exists, but not everyone has voted
    4) The game exists, and this is the last vote
    :param game_request:
    :param dynamodb_table:
    :param twitter_api:
    :return:
    """
    result = dynamodb_table.query(IndexName='CurrentTweetId-index',
                                  Select='ALL_ATTRIBUTES',
                                  KeyConditionExpression=Key('CurrentTweetId').eq(game_request.in_reply_to_status_id))

    # Game does not exist
    if result['Count'] == 0:
        status_message = "@{} the game doesnt exist! Start your own by tweeting @ me with #LetsPlay.".format(game_request.user_name)

        __send_to_twitter(status_message, game_request.status_id, twitter_api)
        # print('Posting \"' + status_message + '\" to user ' + str(game_request.user_name))
        # twitter_api.PostUpdate(status=status_message,
        #                        in_reply_to_status_id=game_request.status_id)
    else:
        game_session = GameSession.NewFromJsonDict(result['Items'][0])

        if any(player for player in game_session.Players if player == game_request.user_name):
            #The player is part of the game

            # Get the current choice
            current_choice = get_choice(game_session.CurrentGameStep)

            print('Current choice and hashtags')
            print(str(current_choice))
            print(game_request.hashtags)

           # Check to see if a valid choice was made
            players_choice = [option for option in current_choice.options if option.key in game_request.hashtags]

            print('players choice')
            print(str(players_choice))
            print('length: ' + str(len(players_choice)))

            if len(players_choice) == 0 or len(players_choice) > 1:
                status_message = "{} you didnt do a valid response! Try again!".format(
                    game_request.user_name)

                __send_to_twitter(status_message, game_request.status_id, twitter_api)
                # print('Posting \"' + status_message + '\" to user ' + str(game_request.user_name))
                # twitter_api.PostUpdate(status=status_message,
                #                        in_reply_to_status_id=game_request.status_id)
            else:
                print(players_choice[0].next_id)

                next_choice = get_choice(players_choice[0].next_id)

                users = " ".join(["@{}".format(player) for player in game_session.Players])

                if hasattr(next_choice, 'options'):
                    choices = " ".join(["#{}".format(option.key) for option in next_choice.options])
                else:
                    choices = ''

                status_message = "{} {} {}".format(users, next_choice.text, choices)

                start_post_status = __send_to_twitter(status_message, None, twitter_api)
                # print('Posting \"' + status_message + '\"')
                # start_post_status = twitter_api.PostUpdate(status=status_message)

                if start_post_status != False:
                    game_session.TwitterSteps += [int(start_post_status.id)]
                    game_session.CurrentTweetId = int(start_post_status.id)
                    game_session.CurrentGameStep = next_choice.id

                    # If they have reached an ending, mark the game as complete
                    if next_choice.is_ending:
                        game_session.GameState = str(GameState.GAME_COMPLETE)

                    dynamodb_table.put_item(Item=game_session.AsDict())

        else:
            # They are not in the game
            status_message = "Hey you! Get out! You're not part of this game! Start your own by tweeting @ me with #LetsPlay.".format(
                game_request.user_name)

            __send_to_twitter(status_message, game_request.status_id, twitter_api)
            # print('Posting \"' + status_message + '\" to user ' + str(game_request.user_name))
            # twitter_api.PostUpdate(status=status_message,
            #                        in_reply_to_status_id=game_request.status_id)



def __send_error_tweet(game_request, twitter_api):
    status_message = "Hello @{}! I could not understand your request!.".format(game_request.user_name)

    __send_to_twitter(status_message, game_request.status_id, twitter_api)
    # print('Posting \"' + status_message + '\" to user ' + str(game_request.user_name))
    # twitter_api.PostUpdate(status=status_message,
    #                        in_reply_to_status_id=game_request.status_id)


def __get_local_dynamo_table():
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2', endpoint_url="http://localhost:8000")
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


if __name__=='__main__':
    twitter_api = MockTwitterApi()
    dynamodb_table = __get_local_dynamo_table()

    print(dynamodb_table.attribute_definitions)

    create_tweet = {
        'user_name': 'rory_jacob',
        'status_message': 'Hello! Its me! Testing!',
        'status_id': 1,
        'in_reply_to_status_id': 2,
        'request_type': str(RequestType.CREATE_GAME)
    }

    join_tweet = {
        'user_name': 'rory_jacob',
        'status_message': 'Hello! Its me! Testing!',
        'status_id': 5,
        'in_reply_to_status_id': 100,
        'request_type': str(RequestType.JOIN_GAME)
    }

    start_tweet = {
        'user_name': 'rory_jacob',
        'status_message': 'Hello! Its me! Testing!',
        'status_id': 5,
        'in_reply_to_status_id': 100,
        'request_type': str(RequestType.START_GAME)
    }

    play_tweet = {
        'user_name': 'rory_jacob',
        'status_message': 'Hello! Its me! Testing!',
        'status_id': 5,
        'in_reply_to_status_id': 100,
        'request_type': str(RequestType.MAKE_SELECTION),
        'hashtags': ['ReadNote']
    }

    handle_game_state([create_tweet, join_tweet, start_tweet, play_tweet], twitter_api, dynamodb_table)

    result = dynamodb_table.scan()
    print('Result: ' + str(result))