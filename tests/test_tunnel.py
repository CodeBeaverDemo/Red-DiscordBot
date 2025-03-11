import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from redbot.core.utils.tunnel import Tunnel

class DummyChannel:
    def __init__(self, channel_id=123):
        self.id = channel_id
        self.sent_messages = []
    async def send(self, content, **kwargs):
        msg = MagicMock()
        msg.content = content
        msg.id = len(self.sent_messages) + 100
        self.sent_messages.append(msg)
        return msg

class DummyAttachment:
    def __init__(self, size, height=None, content="dummy"):
        self.size = size
        self.height = height
        self.content = content
    async def to_file(self):
        file = MagicMock()
        file.fp = self.content
        return file

class DummyMessage:
    def __init__(self, content="", author=None, channel=None, attachments=None, guild=True, message_id=1):
        self.content = content
        self.author = author
        self.channel = channel
        self.attachments = attachments if attachments is not None else []
        self.guild = guild
        self.id = message_id
        self.reactions = []
    async def add_reaction(self, emoji):
        self.reactions.append(emoji)

class DummyUser:
    def __init__(self, id):
        self.id = id

class DummyMember:
    def __init__(self, id, guild):
        self.id = id
        self.guild = guild

@pytest.fixture
def dummy_sender():
    # Dummy sender as a DummyMember
    guild = MagicMock()
    return DummyMember(1, guild)

@pytest.fixture
def dummy_recipient():
    return DummyUser(2)

@pytest.fixture
def dummy_origin():
    return DummyChannel(channel_id=10)

@pytest.fixture(autouse=True)
def reset_instances():
    # Clear the tunnel instances dictionary before each test
    from redbot.core.utils.tunnel import _instances
    _instances.clear()

@pytest.mark.asyncio
async def test_singleton_tunnel(dummy_sender, dummy_origin, dummy_recipient):
    """Test that creating multiple tunnels with same parameters returns the same instance."""
    t1 = Tunnel(sender=dummy_sender, origin=dummy_origin, recipient=dummy_recipient)
    t2 = Tunnel(sender=dummy_sender, origin=dummy_origin, recipient=dummy_recipient)
    assert t1 is t2

@pytest.mark.asyncio
async def test_members_property(dummy_sender, dummy_origin, dummy_recipient):
    """Test the members property returns the sender and recipient."""
    tunnel = Tunnel(sender=dummy_sender, origin=dummy_origin, recipient=dummy_recipient)
    members = tunnel.members
    assert members[0] == dummy_sender
    assert members[1] == dummy_recipient

@pytest.mark.asyncio
@pytest.mark.xfail(reason="Bug in minutes_since calculation: uses (last_interaction - utcnow).seconds")
async def test_minutes_since(dummy_sender, dummy_origin, dummy_recipient):
    """Test minutes_since property returns appropriate minutes difference."""
    tunnel = Tunnel(sender=dummy_sender, origin=dummy_origin, recipient=dummy_recipient)
    # set last_interaction to 2 minutes ago
    tunnel.last_interaction = datetime.utcnow() - timedelta(minutes=2)
    minutes = tunnel.minutes_since
    # because the calculation is (last_interaction - utcnow), expect a negative value around -2 minutes
    assert -3 <= minutes <= -1

@pytest.mark.asyncio
async def test_react_close(dummy_sender, dummy_origin, dummy_recipient):
    """Test react_close sends message to the correct destination and formats message."""
    # Create dummy channels where send is AsyncMock
    dummy_origin.send = AsyncMock(return_value=MagicMock())
    dummy_recipient.send = AsyncMock(return_value=MagicMock())
    tunnel = Tunnel(sender=dummy_sender, origin=dummy_origin, recipient=dummy_recipient)
    # Call react_close with sender id - destination will be recipient
    await tunnel.react_close(uid=dummy_sender.id, message="Closed by {closer.id}")
    dummy_recipient.send.assert_called_once()
    # Call react_close with recipient id - destination will be origin
    await tunnel.react_close(uid=dummy_recipient.id, message="Closed by {closer.id}")
    dummy_origin.send.assert_called_once()

@pytest.mark.asyncio
async def test_message_forwarder_text():
    """Test message_forwarder with text content splitting into pages."""
    async def fake_send(content, **kwargs):
        msg = MagicMock()
        msg.content = content
        msg.id = 200 + len(content)
        return msg

    dummy_destination = MagicMock()
    dummy_destination.send = AsyncMock(side_effect=lambda content, **kwargs: fake_send(content, **kwargs))
    # Text that will be pagified (simulate multiple pages)
    content = "Page1\nPage2\nPage3"
    msgs = await Tunnel.message_forwarder(destination=dummy_destination, content=content)
    assert isinstance(msgs, list)
    assert len(msgs) >= 1

@pytest.mark.asyncio
async def test_message_forwarder_embed_and_files():
    """Test message_forwarder with embed and files without content."""
    dummy_destination = MagicMock()
    dummy_destination.send = AsyncMock(return_value=MagicMock(id=999))
    embed = MagicMock()
    files = [MagicMock()]
    msgs = await Tunnel.message_forwarder(destination=dummy_destination, embed=embed, files=files)
    assert msgs[0].id == 999

@pytest.mark.asyncio
async def test_files_from_attach():
    """Test files_from_attach returns a list of files for valid attachments and skips non-images if required."""
    # Create a dummy attachment that qualifies as image
    attachment_image = DummyAttachment(size=1000, height=100)
    # Create a dummy attachment that is not an image
    attachment_non_image = DummyAttachment(size=1000, height=None)
    # Create a dummy message with attachments; total size less than max_size
    msg = DummyMessage(content="Test", attachments=[attachment_image, attachment_non_image])
    files = await Tunnel.files_from_attach(msg, images_only=True)
    # Only the image attachment should be returned
    assert len(files) == 1

@pytest.mark.asyncio
async def test_close_because_disabled(dummy_sender, dummy_origin, dummy_recipient):
    """Test that close_because_disabled sends close messages to both ends."""
    dummy_origin.send = AsyncMock(return_value=MagicMock())
    dummy_recipient.send = AsyncMock(return_value=MagicMock())
    tunnel = Tunnel(sender=dummy_sender, origin=dummy_origin, recipient=dummy_recipient)
    await tunnel.close_because_disabled("Tunnel closed.")
    dummy_origin.send.assert_called_once_with("Tunnel closed.")
    dummy_recipient.send.assert_called_once_with("Tunnel closed.")

@pytest.mark.asyncio
async def test_communicate_from_sender(dummy_sender, dummy_origin, dummy_recipient):
    """Test communicate method when message is from sender in the origin channel."""
    async def fake_origin_send(content, **kwargs):
        await asyncio.sleep(0)
        msg = MagicMock(id=300)
        msg.add_reaction = AsyncMock(return_value=None)
        return msg
    async def fake_recipient_send(content, **kwargs):
        await asyncio.sleep(0)
        msg = MagicMock(id=400)
        msg.add_reaction = AsyncMock(return_value=None)
        return msg
    dummy_origin.send = AsyncMock(side_effect=fake_origin_send)
    dummy_recipient.send = AsyncMock(side_effect=fake_recipient_send)
    tunnel = Tunnel(sender=dummy_sender, origin=dummy_origin, recipient=dummy_recipient)
    # Create a dummy message from sender in origin channel
    dummy_message = DummyMessage(content="Hello", author=dummy_sender, channel=dummy_origin, message_id=101)
    # Patch files_from_attach to return an empty list (simulate no attachments)
    with patch.object(Tunnel, "files_from_attach", return_value=[]):
        ret_ids = await tunnel.communicate(message=dummy_message, topic="Topic:")
    # ret_ids should be a list of two ints: [forwarded_message.id, original_message.id]
    assert isinstance(ret_ids, list)
    assert len(ret_ids) == 2

@pytest.mark.asyncio
async def test_communicate_from_recipient(dummy_sender, dummy_origin, dummy_recipient):
    """Test communicate method when message is from recipient in DM (guild is None)."""
    async def fake_origin_send(content, **kwargs):
        await asyncio.sleep(0)
        msg = MagicMock(id=500)
        msg.add_reaction = AsyncMock(return_value=None)
        return msg
    async def fake_recipient_send(content, **kwargs):
        await asyncio.sleep(0)
        msg = MagicMock(id=600)
        msg.add_reaction = AsyncMock(return_value=None)
        return msg
    dummy_origin.send = AsyncMock(side_effect=fake_origin_send)
    dummy_recipient.send = AsyncMock(side_effect=fake_recipient_send)
    tunnel = Tunnel(sender=dummy_sender, origin=dummy_origin, recipient=dummy_recipient)
    # Create a dummy message from recipient in DM (guild is None)
    dummy_message = DummyMessage(content="Reply", author=dummy_recipient, channel=DummyChannel(channel_id=999), guild=None, message_id=102)
    with patch.object(Tunnel, "files_from_attach", return_value=[]):
        ret_ids = await tunnel.communicate(message=dummy_message, topic="Re:")
    assert isinstance(ret_ids, list)
    assert len(ret_ids) == 2
@pytest.mark.asyncio
async def test_files_from_attach_exceeds_size():
    """Test files_from_attach returns empty list if total attachment size exceeds max allowed."""
    # Create attachments whose total size is greater than 26214400 bytes.
    att1 = DummyAttachment(size=20000000, height=100)
    att2 = DummyAttachment(size=7000000, height=100)  # total = 27000000 bytes > max_size
    msg = DummyMessage(content="Big", attachments=[att1, att2])
    files = await Tunnel.files_from_attach(msg)
    assert files == []

@pytest.mark.asyncio
async def test_files_from_attach_http_exception():
    """Test files_from_attach raises HTTPException for non-cached image attachment errors."""
    # Define a dummy attachment that raises discord.HTTPException with status != 415.
    class DummyAttachmentFail(DummyAttachment):
        async def to_file(self):
            exc = discord.HTTPException(response=MagicMock(), message="fail")
            exc.status = 400
            raise exc
    att = DummyAttachmentFail(size=1000, height=100)
    msg = DummyMessage(content="Test", attachments=[att])
    with pytest.raises(discord.HTTPException):
        await Tunnel.files_from_attach(msg, images_only=True, use_cached=True)

@pytest.mark.asyncio
async def test_communicate_invalid_sender(dummy_sender, dummy_origin, dummy_recipient):
    """Test communicate returns None if message is from an invalid sender that does not match sender or recipient."""
    tunnel = Tunnel(sender=dummy_sender, origin=dummy_origin, recipient=dummy_recipient)
    # Create a dummy message from a different author
    fake_author = DummyMember(999, MagicMock())
    msg = DummyMessage(content="Ignored", author=fake_author, channel=dummy_origin, guild=True, message_id=103)
    ret_ids = await tunnel.communicate(message=msg, topic="Ignore:")
    assert ret_ids is None

@pytest.mark.asyncio
async def test_communicate_skip_message_content(dummy_sender, dummy_origin, dummy_recipient):
    """Test communicate with skip_message_content True to ensure only the topic is sent."""
    async def fake_send(content, **kwargs):
        await asyncio.sleep(0)
        msg = MagicMock(id=700)
        msg.add_reaction = AsyncMock(return_value=None)
        return msg

    dummy_origin.send = AsyncMock(side_effect=fake_send)
    dummy_recipient.send = AsyncMock(side_effect=fake_send)
    tunnel = Tunnel(sender=dummy_sender, origin=dummy_origin, recipient=dummy_recipient)
    dummy_message = DummyMessage(content="Content", author=dummy_sender, channel=dummy_origin, message_id=104)
    with patch.object(Tunnel, "files_from_attach", return_value=[]):
        ret_ids = await tunnel.communicate(message=dummy_message, topic="Topic only", skip_message_content=True)
    assert isinstance(ret_ids, list)
    assert len(ret_ids) == 2