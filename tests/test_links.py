from mason.telegram.links import message_url
from mason.telegram.models import Chat


def test_public_channel_link():
    chat = Chat(id=-1001234567890, title="Study", kind="channel", username="study_group")
    assert message_url(chat, 42) == "https://t.me/study_group/42"


def test_private_supergroup_link():
    chat = Chat(id=-1001234567890, title="Study", kind="supergroup")
    assert message_url(chat, 42) == "https://t.me/c/1234567890/42"


def test_private_conversation_has_no_fabricated_link():
    chat = Chat(id=123, title="Someone", kind="private", username="someone")
    assert message_url(chat, 42) is None
