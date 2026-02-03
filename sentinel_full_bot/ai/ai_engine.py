import json
import asyncio

async def _read_multiline_input() -> str:
    """
    Reads multiline input from terminal without blocking the event loop.
    Ends on blank line.
    """
    loop = asyncio.get_running_loop()

    def blocking_read():
        lines = []
        while True:
            line = input()
            if not line.strip():
                break
            lines.append(line)
        return "\n".join(lines)

    return await loop.run_in_executor(None, blocking_read)


async def ask_ai(snapshot: dict) -> dict:
    print("\n" + "=" * 80)
    print("AI AUDIT INPUT (paste this into ChatGPT / other AI):\n")
    print(json.dumps(snapshot, indent=2))
    print("\n" + "=" * 80)

    print(
        "\nPaste AI JSON response below.\n"
        "End input with a blank line.\n"
    )

    raw = await _read_multiline_input()

    print("\nAI RAW RESPONSE:")
    print(raw)
    print("=" * 80)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON pasted:\n{e}")
