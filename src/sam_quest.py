from boto3.dynamodb.conditions import Key
import string
import random

from src.game_steps import get_choice
from src.models import GameRequest, RequestType, GameState, GameSession


def handle_game_state(posts, twitter_api, dynamodb_table):

    print('Received ' + str(len(posts)) + ' records')

    for post in posts:

        print('Processing record ' + str(post))
        game_request = GameRequest.NewFromJsonDict(post)

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

            print('length: ' + str(len(players_choice)))

            if len(players_choice) == 0 or len(players_choice) > 1:
                status_message = "{} you didnt do a valid response! Try again!".format(
                    game_request.user_name)

                __send_to_twitter(status_message, game_request.status_id, twitter_api)
                # print('Posting \"' + status_message + '\" to user ' + str(game_request.user_name))
                # twitter_api.PostUpdate(status=status_message,
                #                        in_reply_to_status_id=game_request.status_id)
            else:
                print("Players choice: {}".format(players_choice[0].next_id))

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

