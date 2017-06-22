import unittest
from test_resources import get_twitter_post_processing_table, MockTwitterApi
from src.process_twitter_feed import process_twitter_feed
import boto3
from moto import mock_kinesis, mock_dynamodb2

@mock_kinesis
@mock_dynamodb2
class TestKinesisStreamProcessing(unittest.TestCase):

    def setUp(self):
        self.dynamodb_table = get_twitter_post_processing_table()
        self.twitter_api = MockTwitterApi()
        self.stream_name = 'mock-stream'
        self.kinesis_client = kinesis_client = boto3.client('kinesis')
        kinesis_client.create_stream(StreamName=self.stream_name,
                                     ShardCount=1)

    def test_tweet_processing(self):

        process_twitter_feed(self.twitter_api, self.kinesis_client, self.stream_name, self.dynamodb_table)
        result = self.dynamodb_table.scan()

        print('Result: ' + str(result))

    def tearDown(self):
        self.dynamodb_table = None
        self.kinesis_client = None

if __name__ == '__main__':
    unittest.main()

