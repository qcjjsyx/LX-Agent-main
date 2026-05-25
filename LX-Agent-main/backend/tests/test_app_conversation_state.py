import json
import tempfile
import threading
import unittest
from pathlib import Path

from backend import app as webapp
from backend.agent_runner import AgentRunResult


class FakeRunner:
    def run(self, user_input, session, conversation_id=None, event_logger=None):
        session.messages.append({"role": "user", "content": user_input})
        session.messages.append({"role": "assistant", "content": "fake reply"})
        return AgentRunResult(
            reply="fake reply",
            messages=session.messages,
            manual_workflow_state={"active": True, "stage": f"stage:{conversation_id}"},
            skills=[],
            used_tools=[],
        )


class BlockingRunner:
    def __init__(self):
        self.first_started = threading.Event()
        self.release_first = threading.Event()

    def run(self, user_input, session, conversation_id=None, event_logger=None):
        if user_input == "first":
            self.first_started.set()
            self.release_first.wait(timeout=5)

        session.messages.append({"role": "user", "content": user_input})
        session.messages.append({"role": "assistant", "content": f"reply:{conversation_id}"})
        return AgentRunResult(
            reply=f"reply:{conversation_id}",
            messages=session.messages,
            manual_workflow_state={"active": True, "stage": f"stage:{conversation_id}"},
            skills=[],
            used_tools=[],
        )


class AppConversationStateTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_conversation_dir = webapp.CONVERSATION_DIR
        self.old_current_id = webapp.current_conversation_id
        self.old_messages = webapp.messages
        self.old_manual_state = webapp.manual_workflow_state
        self.old_runner = webapp.agent_runner
        self.old_log_event = webapp.log_event

        webapp.CONVERSATION_DIR = Path(self.temp_dir.name)
        webapp.CONVERSATION_DIR.mkdir(parents=True, exist_ok=True)
        webapp.current_conversation_id = None
        webapp.messages = [webapp.SYSTEM_MESSAGE]
        webapp.manual_workflow_state = None
        webapp.log_event = lambda *args, **kwargs: None

    def tearDown(self):
        webapp.CONVERSATION_DIR = self.old_conversation_dir
        webapp.current_conversation_id = self.old_current_id
        webapp.messages = self.old_messages
        webapp.manual_workflow_state = self.old_manual_state
        webapp.agent_runner = self.old_runner
        webapp.log_event = self.old_log_event
        self.temp_dir.cleanup()

    def test_manual_workflow_state_is_saved_per_conversation(self):
        first_id = webapp.create_new_conversation()
        webapp.manual_workflow_state = {"active": True, "stage": "parser"}
        webapp.save_current_conversation()

        second_id = webapp.create_new_conversation()
        webapp.manual_workflow_state = {"active": True, "stage": "knowledge"}
        webapp.save_current_conversation()

        self.assertTrue(webapp.load_conversation(first_id))
        self.assertEqual(webapp.manual_workflow_state["stage"], "parser")

        self.assertTrue(webapp.load_conversation(second_id))
        self.assertEqual(webapp.manual_workflow_state["stage"], "knowledge")

    def test_chat_uses_requested_conversation_id(self):
        first_id = webapp.create_new_conversation()
        webapp.manual_workflow_state = {"active": True, "stage": "first"}
        webapp.save_current_conversation()

        second_id = webapp.create_new_conversation()
        webapp.manual_workflow_state = {"active": True, "stage": "second"}
        webapp.save_current_conversation()

        webapp.agent_runner = FakeRunner()
        webapp.app.testing = True

        with webapp.app.test_client() as client:
            response = client.post(
                "/chat",
                json={"message": "hello", "conversation_id": first_id},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["conversation_id"], first_id)

        first_data = json.loads(webapp.conversation_path(first_id).read_text(encoding="utf-8"))
        second_data = json.loads(webapp.conversation_path(second_id).read_text(encoding="utf-8"))

        self.assertEqual(first_data["manual_workflow_state"]["stage"], f"stage:{first_id}")
        self.assertEqual(second_data["manual_workflow_state"]["stage"], "second")

    def test_chat_rejects_invalid_conversation_id(self):
        webapp.agent_runner = FakeRunner()
        webapp.app.testing = True

        with webapp.app.test_client() as client:
            response = client.post(
                "/chat",
                json={"message": "hello", "conversation_id": "../outside"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse((Path(self.temp_dir.name).parent / "outside.json").exists())

    def test_overlapping_chats_save_to_their_requested_conversations(self):
        first_id = webapp.create_new_conversation()
        webapp.manual_workflow_state = {"active": True, "stage": "first-start"}
        webapp.save_current_conversation()

        second_id = webapp.create_new_conversation()
        webapp.manual_workflow_state = {"active": True, "stage": "second-start"}
        webapp.save_current_conversation()

        runner = BlockingRunner()
        webapp.agent_runner = runner

        errors = []

        def run_first():
            try:
                webapp.run_agent_once("first", conversation_id=first_id)
            except Exception as exc:
                errors.append(exc)

        first_thread = threading.Thread(target=run_first)
        first_thread.start()
        self.assertTrue(runner.first_started.wait(timeout=5))

        webapp.run_agent_once("second", conversation_id=second_id)
        runner.release_first.set()
        first_thread.join(timeout=5)

        self.assertFalse(first_thread.is_alive())
        self.assertEqual(errors, [])

        first_data = json.loads(webapp.conversation_path(first_id).read_text(encoding="utf-8"))
        second_data = json.loads(webapp.conversation_path(second_id).read_text(encoding="utf-8"))

        self.assertEqual(first_data["manual_workflow_state"]["stage"], f"stage:{first_id}")
        self.assertEqual(second_data["manual_workflow_state"]["stage"], f"stage:{second_id}")
        self.assertEqual(first_data["messages"][-1]["content"], f"reply:{first_id}")
        self.assertEqual(second_data["messages"][-1]["content"], f"reply:{second_id}")


if __name__ == "__main__":
    unittest.main()
