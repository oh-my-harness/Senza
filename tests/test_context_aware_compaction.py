import senza


def test_context_aware_compaction_prompt_returns_tuple():
    result = senza.create_context_aware_compaction_prompt()
    assert isinstance(result, tuple)
    assert len(result) == 2
    system_prompt, user_template = result
    assert isinstance(system_prompt, str)
    assert isinstance(user_template, str)
    assert "{conversation}" in user_template


def test_context_aware_compaction_prompt_usable_in_builder():
    provider = senza.create_openai_provider(api_key="sk-test")
    system_prompt, user_template = senza.create_context_aware_compaction_prompt()
    builder = (
        senza.HarnessBuilder("gpt-4o")
        .provider("*", provider)
        .compaction_prompt(system_prompt, user_template)
    )
    assert builder is not None
