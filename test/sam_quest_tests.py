import unittest
from src.sam_quest import handle_game_state
from src.models import RequestType
from test_resources import get_game_state_table, MockTwitterApi
from moto import mock_dynamodb2

@mock_dynamodb2
class TestSAMQuest(unittest.TestCase):

    def test_tweet_processing(self):
        print('Im here!')
        twitter_api = MockTwitterApi()
        dynamodb_table = get_game_state_table()

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


if __name__ == '__main__':
    unittest.main()
