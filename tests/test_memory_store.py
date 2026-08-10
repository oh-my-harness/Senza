import senza


def test_in_memory_store_creates():
    store = senza.create_in_memory_store("test-source")
    assert store is not None


def test_secure_write_policy_creates():
    policy = senza.create_secure_write_policy()
    assert policy is not None


def test_secure_write_policy_with_config():
    policy = senza.create_secure_write_policy(
        {"max_content_bytes": 8192, "max_ttl_seconds": 3600}
    )
    assert policy is not None
