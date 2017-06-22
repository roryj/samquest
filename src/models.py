from twitter.models import TwitterModel, Status
from enum import Enum

class TwitterGameRequest(TwitterModel):

    def __init__(self, **kwargs):
        self.param_defaults = {
            'user_name': None,
            'status_message': None,
            'status_id': None,
            'in_reply_to_status_id': None,
            'request_type': None,
            'hashtags': []
        }

        for (param, default) in self.param_defaults.items():
            setattr(self, param, kwargs.get(param, default))

        # if 'request_type' in kwargs:
        #     self.request_type = RequestType(kwargs.get('request_type'))

class GameSession(TwitterModel):
    def __init__(self, **kwargs):
        self.param_defaults = {
            'TweetStartId': None,
            'GameState': None,
            'GameCreator': None,
            'Players': None,
            'CurrentTweetId': None,
            'CurrentVotes': None,
            'CurrentGameStep': None,
            'TwitterSteps': None
        }

        for (param, default) in self.param_defaults.items():
            setattr(self, param, kwargs.get(param, default))

class RequestType(Enum):
    CREATE_GAME='CREATE_GAME'
    START_GAME='START_GAME'
    JOIN_GAME='JOIN_GAME'
    MAKE_SELECTION='MAKE_SELECTION'
    HELP='HELP'
    UNKNOWN='UNKNOWN'

    def __str__(self):
        return self.name

class GameState(Enum):
    PENDING_GAME_START='PENDING_GAME_START'
    PLAYING='PLAYING'
    PENDING_GAME_INPUT='PENDING_GAME_INPUT'
    GAME_COMPLETE='GAME_COMPLETE'

    def __str__(self):
        return self.name

class MockTwitterApi():
    def GetMentions(self):
        pass
    def PostUpdate(self, status, in_reply_to_status_id=None):

        if len(status) > 140:
            raise ('Too many characters!')

        return Status.NewFromJsonDict({'id': 100})
