"""03 — Sandbox: Seatbelt (macOS) / Bwrap (Linux).

Demonstrates:
  - create_seatbelt_sandbox: macOS sandbox-exec wrapper
  - create_bwrap_sandbox: Linux bubblewrap wrapper
  - Sandbox.start() / Sandbox.is_running() lifecycle

Sandbox isolates tool execution (bash, file writes) from the host system.
On macOS, Seatbelt uses sandbox-exec profiles; on Linux, Bwrap uses
namespace unsharing. Both restrict filesystem writes, network access, and
process spawning.
"""

import os
import platform

import senza


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "sk-test")
    provider = senza.providers.openai(api_key=api_key)
    env = senza.create_os_env(".")

    system = platform.system()
    if system == "Darwin":
        config = {
            "read_only_paths": ["/usr", "/bin", "/lib"],
            "write_only_paths": ["/tmp/senza-sandbox"],
            "no_network": True,
        }
        sandbox = senza.infra.seatbelt_sandbox(config=config)
        print("SeatbeltSandbox created (macOS).")
    else:
        config = {
            "readonly": ["/usr", "/bin"],
            "bind": {"/tmp/senza-sandbox": "/tmp"},
            "unshare_net": True,
        }
        sandbox = senza.infra.bwrap_sandbox(config=config)
        print("BwrapSandbox created (Linux).")

    print(f"  is_running (pre-start): {sandbox.is_running()}")

    harness = senza.HarnessBuilder("gpt-4o").provider("*", provider).env(env).build()

    print(f"Harness phase: {harness.phase()}")
    print(f"  is_running (post-build): {sandbox.is_running()}")


if __name__ == "__main__":
    main()
