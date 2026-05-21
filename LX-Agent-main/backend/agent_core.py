import os

import dotenv
from openai import OpenAI

try:
    from .agent_runner import AgentRunner, AgentSession
except ImportError:  # pragma: no cover - supports direct script execution
    from agent_runner import AgentRunner, AgentSession


dotenv.load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are a local AI Agent. Use the currently enabled tools when they "
        "are relevant to the user's task. If no tool is relevant, answer "
        "directly and clearly."
    ),
}


def start_agent():
    print("\n[AI Agent started]")
    user_input = input("\nTask: ")

    runner = AgentRunner(
        client=client,
        model=MODEL,
        base_dir=os.getcwd(),
        system_message=SYSTEM_MESSAGE,
    )
    session = AgentSession(messages=[SYSTEM_MESSAGE])
    result = runner.run(user_input=user_input, session=session, conversation_id="cli")

    print(f"\nAssistant:\n{result.reply}")
    print("\nDone.")
