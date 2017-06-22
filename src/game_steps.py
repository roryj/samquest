from twitter.models import TwitterModel

class Choice(TwitterModel):
    def __init__(self, **kwargs):
        self.param_defaults = {
            'id': None,
            'text': None,
            'is_ending': False,
            'options': []
        }

        for (param, default) in self.param_defaults.items():
            if param != 'options':
                setattr(self, param, kwargs.get(param, default))

        if 'options' in kwargs:
            self.options = [Option.NewFromJsonDict(x) for x in kwargs.get('options', [])]

    def __str__(self):
        return self.text


class Option(TwitterModel):
    def __init__(self, **kwargs):
        self.param_defaults = {
            'key': None,
            'next_id': None
        }

        for (param, default) in self.param_defaults.items():
            setattr(self, param, kwargs.get(param, default))


SITUATIONS = {
    1: Choice.NewFromJsonDict(
            {
                'id': 1,
                'text': 'A tree is in the distance, a note on the floor.',
                'options':
                    [
                        {
                            'key': 'ReadNote',
                            'next_id': 2
                        },
                        {
                            'key': 'Tree',
                            'next_id': 3
                        }
                    ]
            }
        ),
    2: Choice.NewFromJsonDict(
            {
                'id': 2,
                'text': 'The note says: "Hello my lost love." The tree beacons, wistfully.',
                'options':
                    [
                        {
                            'key': 'ReadNote',
                            'next_id': 4
                        },
                        {
                            'key': 'Tree',
                            'next_id': 3
                        }
                    ]
            }
        ),
    3: Choice.NewFromJsonDict(
            {
                'id': 3,
                'text': 'You are at the base of the tree. It is big.',
                'options':
                    [
                        {
                            'key': 'Stare',
                            'next_id': 7
                        },
                        {
                            'key': 'Listen',
                            'next_id': 6
                        }
                    ]
            }
        ),
    4: Choice.NewFromJsonDict(
            {
                'id': 4,
                'text': 'The note continues: "milk, sugar, peanut butter". THE TREE PLEASE',
                'options':
                    [
                        {
                            'key': 'ReadNote',
                            'next_id': 5
                        },
                        {
                            'key': 'Tree',
                            'next_id': 3
                        }
                    ]
            }
        ),
    5: Choice.NewFromJsonDict(
            {
                'id': 5,
                'text': 'The note continues: "I am out of things to write about". The tree is impatient',
                'options':
                    [
                        {
                            'key': 'Tree',
                            'next_id': 3
                        },
                        {
                            'key': 'TreeAgain',
                            'next_id': 3
                        }
                    ]
            }
        ),
    6: Choice.NewFromJsonDict(
            {
                'id': 6,
                'text': 'You lean in close, and the tree whispers... Nothing, it is a tree. #TheEnd',
                'is_ending': True
            }
        ),
    7: Choice.NewFromJsonDict(
        {
            'id': 7,
            'text': 'You stare. So hard. The tree stands there. #TheEnd',
            'is_ending': True
        }
    )
}

def get_choice(choice_id):

    if choice_id in SITUATIONS:
        return SITUATIONS[choice_id]
    else:
        raise ('This situation doesnt exist!')

