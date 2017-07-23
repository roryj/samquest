from time import sleep

from boto3.dynamodb.conditions import Key, Attr
from src.models import GameRequest, GameState, RequestType
from twitter.error import TwitterError

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

    try:
        for post in twitter_api.GetMentions(since_id=last_processed_tweet_id):
            print(str(post))

            user = twitter_api.GetUser(user_id=post.user.id)

            hashtags = [tag.text.lower() for tag in post.hashtags]

            print(hashtags)

            if 'help' in hashtags:
                request_type = RequestType.HELP
            elif 'letsplay' in hashtags:
                request_type = RequestType.CREATE_GAME
            elif 'startgame' in hashtags:
                request_type = RequestType.START_GAME
            elif 'joingame' in hashtags:
                request_type = RequestType.JOIN_GAME
            elif 'chooseme' in hashtags:
                request_type = RequestType.MAKE_SELECTION
            else:
                request_type = RequestType.UNKNOWN

            game_request = GameRequest.NewFromJsonDict({'user_name': user.screen_name,
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
    except TwitterError as e:
        if 'Rate limit exceeded' in e.message:
            print('Got rate limited by twitter :(. Sleeping for 20 seconds')
            sleep(20)
        else:
            print(str(e))

    if last_post_id is not None:
        dynamo_table.put_item(Item={'TwitterAccount': '@SAMQuest9', 'TwitterPostId': last_post_id})

    print('Done processing twitter posts.')


