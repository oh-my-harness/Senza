"""22 — FS Tools: bash/read/write/edit/grep/glob (FsToolsPlugin).

Mirrors runtime `22_fs_tools.rs`. Demonstrates `senza.create_fs_tools_plugin()`,
which auto-registers the six fs tools (read / write / edit / bash / grep / glob)
backed by a shared `FileSnapshotStore` (read records a `[PATH#TAG]` anchor that
`edit` uses for staleness detection). The plugin must be paired with an OS
execution environment via `senza.create_os_env(working_dir)`.

We run 3 prompts inside one temp working dir:
  - Part 1: BashTool — the LLM runs `echo hello > test.txt` and cats it back.
  - Part 2: WriteTool + ReadTool — the LLM writes `greeting.txt` and reads it.
  - Part 3: GrepTool + GlobTool — pre-created `.rs` files are searched with
    `grep` and listed with `glob`, and the LLM reports what it found.

Run:
  source ~/.omp_llm_env && python live-tests/examples/22_fs_tools.py
"""

import os
import tempfile

import senza
from _common import make_example_harness, run_prompt, text_of


def collect_tool_calls(events):
    """Return the list of tool names invoked during a run."""
    return [e.get("tool_name", "?") for e in events if e.get("type") == "tool_call_start"]


def part1_bash(harness, workdir):
    print("--- Part 1: BashTool (echo hello > test.txt) ---\n")
    prompt = (
        "Use the bash tool to run this exact command: echo hello > test.txt "
        "Then confirm the file was created by running: cat test.txt"
    )
    print(f"LLM prompt: {prompt}")
    events = run_prompt(harness, prompt, timeout_ms=60_000)

    tools = collect_tool_calls(events)
    test_txt = os.path.join(workdir, "test.txt")
    exists = os.path.exists(test_txt)
    content = ""
    if exists:
        with open(test_txt) as f:
            content = f.read().strip()

    print(f"\nTools called: {tools}")
    print(f"test.txt exists: {exists}")
    print(f"test.txt content: {content!r}")
    print(f"Final text: {text_of(events).strip()[:160]}")
    print("\nObservation:")
    print(f"  bash tool called: {'bash' in tools}")
    print(f"  file created:     {exists}")
    print(f"  file content:     {content!r}")


def part2_write_read(harness, workdir):
    print("\n--- Part 2: WriteTool + ReadTool (round-trip) ---\n")
    prompt = (
        "Use the write tool to create a file named 'greeting.txt' with the content "
        "'Hello from WriteTool!'. Then use the read tool to read the file back "
        "and tell me what it contains."
    )
    print(f"LLM prompt: {prompt}")
    events = run_prompt(harness, prompt, timeout_ms=60_000)

    tools = collect_tool_calls(events)
    greeting = os.path.join(workdir, "greeting.txt")
    content = ""
    if os.path.exists(greeting):
        with open(greeting) as f:
            content = f.read().strip()

    print(f"\nTools called: {tools}")
    print(f"greeting.txt content: {content!r}")
    print(f"Final text: {text_of(events).strip()[:160]}")
    print("\nObservation:")
    print(f"  write tool called: {'write' in tools}")
    print(f"  read tool called:  {'read' in tools}")
    print(f"  file content:      {content!r}")


def part3_grep_glob(harness, workdir):
    print("\n--- Part 3: GrepTool + GlobTool ---\n")
    # Pre-create several files in the temp dir for the LLM to search.
    for name, body in [
        ("alpha.rs", 'fn alpha() { println!("alpha"); }\n'),
        ("beta.rs", 'fn beta() { println!("beta"); }\n'),
        ("gamma.rs", 'fn gamma() { println!("gamma"); }\n'),
    ]:
        with open(os.path.join(workdir, name), "w") as f:
            f.write(body)
    print("Pre-created: alpha.rs, beta.rs, gamma.rs")

    prompt = (
        "You have access to grep and glob tools. Do two things:\n"
        "1. Use the grep tool to search for the pattern 'fn ' in the current "
        'directory (paths: ["."]).\n'
        "2. Use the glob tool to list all files matching the pattern '**/*.rs' "
        '(paths: ["**/*.rs"]).\n'
        "Report what you found from each tool."
    )
    print(f"LLM prompt: {prompt}")
    events = run_prompt(harness, prompt, timeout_ms=60_000)

    tools = collect_tool_calls(events)
    print(f"\nTools called: {tools}")
    print(f"Final text: {text_of(events).strip()[:200]}")
    print("\nObservation:")
    print(f"  grep tool called: {'grep' in tools}")
    print(f"  glob tool called: {'glob' in tools}")
    print(f"  both tools used:  {'grep' in tools and 'glob' in tools}")


def main() -> None:
    print("=== 22: FS Tools (bash/read/write/edit/grep/glob) ===\n")

    with tempfile.TemporaryDirectory() as workdir:
        harness = make_example_harness(
            lambda b: (
                b.plugin(senza.create_fs_tools_plugin())
                .env(senza.create_os_env(workdir))
                .system_prompt(
                    "You are a coding assistant with access to read, write, edit, "
                    "bash, grep and glob file tools. Use them to inspect and modify "
                    "files in the working directory, then answer from what you read."
                )
            )
        )

        part1_bash(harness, workdir)
        part2_write_read(harness, workdir)
        part3_grep_glob(harness, workdir)

        print("\n--- Summary ---")
        print("Part 1: bash tool creates a file via shell redirect")
        print("Part 2: write + read round-trip file content")
        print("Part 3: grep searches content, glob lists matching files")


if __name__ == "__main__":
    main()
