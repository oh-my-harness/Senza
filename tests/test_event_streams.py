import senza


def test_webhook_stream_creates():
    channel, stream = senza.strategy.webhook_stream(buffer=16)
    assert channel is not None
    assert stream is not None


def test_webhook_channel_push():
    import asyncio

    channel, stream = senza.strategy.webhook_stream(buffer=4)
    channel.push({"event": "test", "data": "hello"})
