import os
import base64
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from core.tools import TOOLS, ToolExecutor
from core.router import Router
from core.local_intents import clarification_for, detect_local_tool, pending_slot_for
from services.shared_workspace import SharedWorkspace
from services.file_reader import read_text_file
from services.local_model import LocalModelClient
from services.session_registry import SessionRegistry
from memory.user_memory import UserMemory
from services.llm_client import LLMClient
from services.reminder_manager import ReminderManager
from services.task_manager import TaskManager
from services.daily_briefing import DailyBriefingService
from services.weather_service import describe_weather_code, get_weather
from services.gmail_reader import _decode_message_part


class DummyContext:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


class DummyMemory:
    pass


class ConversationPromptTests(unittest.TestCase):
    def test_latest_standalone_question_and_obvious_typo_are_prioritized(self):
        prompt = LLMClient()._system_prompt("")

        self.assertIn("en son kullanıcı mesajını asıl istek kabul et", prompt)
        self.assertIn("'kunatumu açıkla' -> 'kuantumu açıkla'", prompt)
        self.assertIn("yeni ve bağımsız bir soruyu eski dosya/komut", prompt)


class RateLimitFallbackTests(unittest.TestCase):
    class Response:
        def __init__(self, status_code, data=None, headers=None, text=""):
            self.status_code = status_code
            self._data = data or {}
            self.headers = headers or {}
            self.text = text

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.status_code)

        def json(self):
            return self._data

    @patch("services.llm_client.requests.post")
    def test_daily_limit_tries_next_model(self, post):
        post.side_effect = [
            self.Response(
                429,
                headers={"x-ratelimit-remaining-requests": "0"},
                text="Requests per day limit reached",
            ),
            self.Response(
                200,
                data={"choices": [{"message": {"content": "Yedek model çalıştı"}}]},
            ),
        ]
        client = LLMClient()
        with patch("services.llm_client.config.MODEL", "model-a"), patch(
            "services.llm_client.config.MODEL_FALLBACKS", ["model-a", "model-b"]
        ):
            result = client._call_api(
                [{"role": "user", "content": "merhaba"}],
                with_tools=False,
            )
        self.assertEqual("Yedek model çalıştı", result["message"]["content"])
        self.assertEqual("model-b", client._active_model)

    @patch("services.llm_client.requests.post")
    def test_exhausted_daily_limit_reports_reset(self, post):
        post.return_value = self.Response(
            429,
            headers={
                "x-ratelimit-remaining-requests": "0",
                "x-ratelimit-reset-requests": "4h12m",
            },
            text="Requests per day limit reached",
        )
        client = LLMClient()
        with patch("services.llm_client.config.MODEL", "model-a"), patch(
            "services.llm_client.config.MODEL_FALLBACKS", ["model-a", "model-b"]
        ):
            result = client._call_api(
                [{"role": "user", "content": "merhaba"}],
                with_tools=False,
            )
        self.assertIn("günlük kullanım sınırına", result["message"]["content"])
        self.assertIn("4h12m", result["message"]["content"])


class ToolContractTests(unittest.TestCase):
    def test_every_declared_tool_has_a_unique_handler(self):
        names = [tool["function"]["name"] for tool in TOOLS]
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertTrue(
                hasattr(ToolExecutor, f"_{name}"),
                f"{name} için ToolExecutor metodu eksik",
            )

    def test_core_personal_assistant_tools_are_declared(self):
        names = {tool["function"]["name"] for tool in TOOLS}
        expected = {
            "create_reminder",
            "list_reminders",
            "cancel_reminder",
            "get_weather",
            "read_email",
            "create_calendar_event",
            "update_calendar_event",
            "delete_calendar_event",
            "add_task",
            "list_tasks",
            "complete_task",
            "add_note",
            "list_notes",
            "get_daily_briefing",
        }
        self.assertTrue(expected.issubset(names))


class ReminderManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "reminders.json")
        self.manager = ReminderManager(self.path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reminder_persists_and_can_be_cancelled(self):
        due = (datetime.now().astimezone() + timedelta(minutes=10)).isoformat()
        item = self.manager.add("Kahveyi kontrol et", due)

        reloaded = ReminderManager(self.path)
        self.assertEqual(item["id"], reloaded.pending()[0]["id"])
        cancelled = reloaded.cancel(reminder_id=item["id"])
        self.assertEqual("cancelled", cancelled["status"])
        self.assertEqual([], reloaded.pending())

    def test_due_reminder_is_delivered_only_once(self):
        future = datetime.now().astimezone() + timedelta(minutes=1)
        item = self.manager.add("Fırına bak", future.isoformat())
        delivered = self.manager.pop_due(future + timedelta(seconds=1))

        self.assertEqual(item["id"], delivered[0]["id"])
        self.assertEqual([], self.manager.pop_due(future + timedelta(seconds=2)))

    def test_past_reminder_is_rejected(self):
        past = datetime.now().astimezone() - timedelta(seconds=1)
        with self.assertRaises(ValueError):
            self.manager.add("Geçmiş", past.isoformat())


class TaskManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "tasks.json")
        self.manager = TaskManager(self.path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_task_persists_and_can_be_completed(self):
        item = self.manager.add_task("Raporu bitir")
        reloaded = TaskManager(self.path)
        self.assertEqual(item["id"], reloaded.pending_tasks()[0]["id"])
        completed = reloaded.complete_task(query="raporu")
        self.assertEqual("completed", completed["status"])
        self.assertEqual([], reloaded.pending_tasks())

    def test_note_can_be_searched(self):
        self.manager.add_note("Proje rengi mor olacak")
        self.manager.add_note("Kahve al")
        results = self.manager.notes("proje")
        self.assertEqual(1, len(results))
        self.assertIn("mor", results[0]["text"])

    def test_note_tags_and_non_matching_query_keep_notes_discoverable(self):
        self.manager.add_note(
            "Arayüzün ana rengi mor olacak",
            tags=["proje", "arayüz", "tasarım"],
        )
        tagged = self.manager.notes("proje")
        self.assertEqual("Arayüzün ana rengi mor olacak", tagged[0]["text"])

        suggestions = self.manager.notes("bütçe")
        self.assertTrue(suggestions[0]["_suggestion"])

    def test_duplicate_note_is_not_added_twice(self):
        first = self.manager.add_note("Arayüzün ana rengi mor olacak")
        duplicate = self.manager.add_note(
            "  arayüzün   ANA rengi mor olacak  ",
            tags=["proje"],
        )
        self.assertTrue(duplicate["_duplicate"])
        self.assertEqual(first["id"], duplicate["id"])
        self.assertEqual(1, len(self.manager.notes()))

    def test_project_query_matches_interface_note_semantically(self):
        self.manager.add_note("Arayüzün ana rengi mor olacak")
        results = self.manager.notes("proje")
        self.assertEqual(1, len(results))
        self.assertFalse(results[0].get("_suggestion", False))
        self.assertIn("proje", results[0]["tags"])


class DailyBriefingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tasks = TaskManager(os.path.join(self.temp_dir.name, "tasks.json"))
        self.reminders = ReminderManager(
            os.path.join(self.temp_dir.name, "reminders.json")
        )
        self.service = DailyBriefingService(
            self.tasks,
            self.reminders,
            os.path.join(self.temp_dir.name, "briefing.json"),
            os.path.join(self.temp_dir.name, "briefing_config.json"),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_briefing_is_shown_only_once_per_slot_and_day(self):
        morning = datetime(2026, 8, 4, 8, 0).astimezone()
        evening = datetime(2026, 8, 4, 20, 0).astimezone()
        self.assertTrue(self.service.should_show(morning))
        self.service.mark_shown(morning)
        self.assertFalse(self.service.should_show(morning))
        self.assertTrue(self.service.should_show(evening))

    def test_evening_briefing_contains_local_tasks_without_weather(self):
        self.tasks.add_task("Raporu tamamla")
        evening = datetime(2026, 8, 4, 20, 0).astimezone()
        result = self.service.build(evening)
        self.assertIn("Akşam özeti", result)
        self.assertIn("Raporu tamamla", result)
        self.assertNotIn("Hava bilgisi", result)

    def test_overdue_task_is_marked_in_briefing(self):
        self.tasks.add_task("Eski görev", "2026-08-03T10:00:00+03:00")
        evening = datetime(2026, 8, 4, 20, 0).astimezone()
        result = self.service.build(evening)
        self.assertIn("GECİKMİŞ", result)

    def test_user_can_disable_morning_briefing_and_change_city(self):
        morning = datetime(2026, 8, 4, 8, 0).astimezone()
        saved = self.service.update_settings(
            morning_enabled=False,
            city="Ankara",
        )
        self.assertEqual("Ankara", saved["city"])
        self.assertFalse(self.service.should_show(morning))
        self.assertEqual("Ankara", self.service.get_settings()["city"])


class LocalIntentTests(unittest.TestCase):
    def test_clear_list_commands_are_routed_locally(self):
        self.assertEqual(("list_tasks", {}), detect_local_tool("Görevlerimi göster"))
        self.assertEqual(
            ("list_reminders", {}),
            detect_local_tool("hatırlatıcılarımı listele"),
        )
        self.assertEqual(
            ("list_user_memory", {}),
            detect_local_tool("Benim hakkımda ne biliyorsun?"),
        )

    def test_note_topic_is_extracted_without_model(self):
        self.assertEqual(
            ("list_notes", {"query": "proje"}),
            detect_local_tool("Proje hakkındaki notlarımı göster"),
        )

    def test_ambiguous_conversation_is_left_to_model(self):
        self.assertIsNone(detect_local_tool("Proje hakkında ne düşünüyorsun?"))

    def test_safe_write_commands_are_parsed_locally(self):
        self.assertEqual(
            ("add_note", {"text": "arayüz mor olacak", "tags": []}),
            detect_local_tool("Not al: arayüz mor olacak"),
        )
        self.assertEqual(
            ("add_task", {"title": "kahve al", "due_at": ""}),
            detect_local_tool("Yapılacaklara kahve al ekle"),
        )
        self.assertEqual(
            ("complete_task", {"task_id": "", "query": "alışveriş"}),
            detect_local_tool("Alışveriş görevini tamamla"),
        )

    def test_city_weather_is_parsed_locally(self):
        self.assertEqual(
            ("get_weather", {"city": "Ankara", "period": "today"}),
            detect_local_tool("Ankara hava durumunu göster"),
        )

    def test_incomplete_actions_return_targeted_clarification(self):
        self.assertIn("hangi tarih", clarification_for("hatırlatıcı oluştur"))
        self.assertIn("kime", clarification_for("mail gönder"))
        self.assertIn("Hangi dosyayı", clarification_for("dosyayı sil"))
        self.assertEqual("note", pending_slot_for("not al"))


class SharedWorkspaceTests(unittest.TestCase):
    def test_sessions_share_results_but_can_exclude_their_own(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = SharedWorkspace(os.path.join(folder, "shared.json"))
            workspace.publish("chat-1", "code", "Kod üretildi", "app.py hazır")
            workspace.publish("chat-2", "research", "Araştırma", "Kaynak bulundu")

            visible = workspace.recent(exclude_session="chat-2")
            self.assertEqual(1, len(visible))
            self.assertEqual("chat-1", visible[0]["session_id"])
            self.assertIn("app.py", workspace.formatted_context("chat-2"))


class FileReaderTests(unittest.TestCase):
    def test_small_code_file_can_be_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "sample.py")
            Path(path).write_text("print('merhaba')", encoding="utf-8")
            result = read_text_file(path)
            self.assertEqual("sample.py", result["name"])
            self.assertIn("merhaba", result["content"])

    def test_sensitive_and_binary_files_are_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            secret = os.path.join(folder, ".env")
            Path(secret).write_text("SECRET=x", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_text_file(secret)
            binary = os.path.join(folder, "sample.txt")
            Path(binary).write_bytes(b"abc\x00def")
            with self.assertRaises(ValueError):
                read_text_file(binary)


class LocalModelTests(unittest.TestCase):
    @patch("services.local_model.requests.post")
    def test_optional_ollama_client_returns_local_answer(self, post):
        response = post.return_value
        response.raise_for_status.return_value = None
        response.json.return_value = {"message": {"content": "Yerel cevap"}}
        client = LocalModelClient("qwen3:8b")
        self.assertEqual("Yerel cevap", client.chat([{"role": "user", "content": "selam"}]))

    def test_empty_local_model_is_disabled(self):
        client = LocalModelClient("")
        self.assertFalse(client.enabled)
        self.assertIsNone(client.chat([]))


class PayloadCompactionTests(unittest.TestCase):
    def test_plain_chat_sends_no_tool_schema(self):
        tools = LLMClient._relevant_tools([{"role": "user", "content": "selam"}])
        self.assertEqual([], tools)

    def test_task_message_only_selects_task_tools(self):
        tools = LLMClient._relevant_tools(
            [{"role": "user", "content": "görevlerimi göster"}]
        )
        names = {item["function"]["name"] for item in tools}
        self.assertIn("list_tasks", names)
        self.assertNotIn("send_email", names)

    def test_long_history_is_compacted(self):
        messages = [{"role": "system", "content": "s" * 12000}]
        messages.extend(
            {"role": "user", "content": str(index) + "x" * 7000}
            for index in range(8)
        )
        compact = LLMClient._compact_initial_context(messages)
        self.assertLess(sum(len(item["content"]) for item in compact), 28000)
        self.assertTrue(compact[-1]["content"].startswith("7") or "7" in compact[-1]["content"])


class SessionRegistryTests(unittest.TestCase):
    def test_custom_session_name_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "names.json")
            registry = SessionRegistry(path)
            self.assertEqual("Kodlama", registry.rename("chat-2", "  Kodlama  "))
            self.assertEqual("Kodlama", SessionRegistry(path).name_for("chat-2"))

    def test_empty_session_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = SessionRegistry(os.path.join(folder, "names.json"))
            with self.assertRaises(ValueError):
                registry.rename("chat-1", "   ")


class WeatherServiceTests(unittest.TestCase):
    def test_wmo_code_is_translated(self):
        self.assertEqual("gök gürültülü fırtına", describe_weather_code(95))

    @patch("services.weather_service.requests.get")
    def test_current_weather_uses_geocoded_location(self, get):
        class Response:
            def __init__(self, data):
                self.data = data

            def raise_for_status(self):
                return None

            def json(self):
                return self.data

        get.side_effect = [
            Response({
                "results": [{
                    "name": "Elazığ",
                    "admin1": "Elazığ",
                    "latitude": 38.67,
                    "longitude": 39.22,
                }]
            }),
            Response({
                "current": {
                    "weather_code": 2,
                    "temperature_2m": 24,
                    "apparent_temperature": 23,
                    "relative_humidity_2m": 40,
                    "wind_speed_10m": 8,
                },
                "daily": {},
            }),
        ]

        result = get_weather("Elazığ", "now")
        self.assertIn("parçalı bulutlu", result)
        self.assertIn("24°C", result)
        self.assertEqual(2, get.call_count)


class GoogleIntegrationTests(unittest.TestCase):
    def test_plain_text_mail_part_is_decoded(self):
        encoded = base64.urlsafe_b64encode("Merhaba Heko".encode()).decode()
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": encoded},
                }
            ],
        }
        self.assertEqual("Merhaba Heko", _decode_message_part(payload))

    def test_calendar_write_waits_for_confirmation(self):
        executor = ToolExecutor(DummyMemory(), DummyContext())
        result = executor.execute(
            "create_calendar_event",
            {
                "title": "Toplantı",
                "start_at": "2026-07-31T10:00:00+03:00",
                "end_at": "2026-07-31T11:00:00+03:00",
            },
        )
        self.assertIn("ONAY_GEREKLİ", result)
        self.assertIn("Toplantı", executor.pending_action_info()["summary"])


class ToolConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.executor = ToolExecutor(DummyMemory(), DummyContext())
        self.calls = []
        self.executor._delete_file = self._record_delete

    def _record_delete(self, args):
        self.calls.append(args)
        return "executed"

    def test_high_risk_tool_waits_for_confirmation(self):
        result = self.executor.execute("delete_file", {"query": "rapor.txt"})

        self.assertIn("ONAY_GEREKLİ", result)
        self.assertEqual([], self.calls)

        confirmed = self.executor.execute("confirm_pending_action", {})
        self.assertEqual("executed", confirmed)
        self.assertEqual([{"query": "rapor.txt"}], self.calls)

    def test_cancel_does_not_execute_pending_action(self):
        self.executor.execute("delete_file", {"query": "rapor.txt"})
        result = self.executor.execute("cancel_pending_action", {})

        self.assertIn("İptal edildi", result)
        self.assertEqual([], self.calls)
        self.assertIsNone(self.executor._pending_action)

    def test_expired_confirmation_is_not_executed(self):
        self.executor.execute("delete_file", {"query": "rapor.txt"})
        self.executor._pending_action["expires_at"] = time.monotonic() - 1

        result = self.executor.execute("confirm_pending_action", {})
        self.assertIn("süresi doldu", result)
        self.assertEqual([], self.calls)

    def test_expired_action_reports_timeout_even_when_cancelled(self):
        self.executor.execute("delete_file", {"query": "rapor.txt"})
        self.executor._pending_action["expires_at"] = time.monotonic() - 1

        result = self.executor.execute("cancel_pending_action", {})

        self.assertIn("süresi doldu", result)
        self.assertNotIn("İptal edildi", result)
        self.assertEqual([], self.calls)
        self.assertIsNone(self.executor._pending_action)

    def test_second_risky_action_cannot_replace_pending_action(self):
        self.executor.execute("delete_file", {"query": "ilk.txt"})
        result = self.executor.execute(
            "send_email",
            {
                "to": "test@example.com",
                "subject": "Konu",
                "body": "İçerik",
            },
        )

        self.assertIn("Önce mevcut", result)
        self.executor.execute("confirm_pending_action", {})
        self.assertEqual([{"query": "ilk.txt"}], self.calls)

    def test_invalid_email_is_not_sent_after_confirmation(self):
        result = self.executor.execute(
            "send_email",
            {"to": "geçersiz", "subject": "Konu", "body": "İçerik"},
        )
        self.assertIn("ONAY_GEREKLİ", result)

        confirmed = self.executor.execute("confirm_pending_action", {})
        self.assertIn("Geçerli bir alıcı", confirmed)


class RouterConfirmationTests(unittest.TestCase):
    def test_explicit_confirmation_bypasses_model(self):
        router = Router.__new__(Router)
        router.context = DummyContextWithMessages()
        router.executor = ToolExecutor(DummyMemory(), router.context)
        router.executor._delete_file = lambda args: "çöp kutusuna taşındı"
        router.executor.execute("delete_file", {"query": "rapor.txt"})
        router.last_tools_used = []

        response = router.get_response("onaylıyorum")

        self.assertEqual("çöp kutusuna taşındı", response)
        self.assertFalse(router.executor.has_pending_action())

    def test_expired_action_reports_timeout_for_no_answer(self):
        router = Router.__new__(Router)
        router.context = DummyContextWithMessages()
        router.executor = ToolExecutor(DummyMemory(), router.context)
        router.executor._delete_file = lambda args: "çöp kutusuna taşındı"
        router.executor.execute("delete_file", {"query": "rapor.txt"})
        router.executor._pending_action["expires_at"] = time.monotonic() - 1
        router.last_tools_used = []

        response = router.get_response("hayır")

        self.assertIn("süresi doldu", response)
        self.assertFalse(router.executor.has_pending_action())


class DummyContextWithMessages(DummyContext):
    def __init__(self):
        super().__init__()
        self.messages = []

    def add_message(self, role, content):
        self.messages.append((role, content))


class UserMemoryV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_path = UserMemory._SAVE_PATH
        UserMemory._SAVE_PATH = os.path.join(
            self.temp_dir.name, "user_memory.json"
        )

    def tearDown(self):
        UserMemory._SAVE_PATH = self.old_path
        self.temp_dir.cleanup()

    def test_metadata_is_persisted_and_reloaded(self):
        memory = UserMemory()
        memory.add_to("preferences", "Koyu tema", source="test")

        entries = memory.get_entries()
        self.assertEqual(1, len(entries))
        self.assertEqual("test", entries[0]["source"])
        self.assertIn("updated_at", entries[0])

        reloaded = UserMemory()
        self.assertEqual(["Koyu tema"], reloaded.get_category("preferences"))
        self.assertEqual(1, len(reloaded.get_entries()))

    def test_exact_memory_can_be_removed(self):
        memory = UserMemory()
        memory.add_to("goals", "Python öğrenmek")
        memory.add_to("goals", "İngilizce geliştirmek")

        self.assertTrue(memory.remove("goals", "Python öğrenmek"))
        self.assertEqual(
            ["İngilizce geliştirmek"],
            memory.get_category("goals"),
        )
        self.assertFalse(memory.remove("goals", "olmayan kayıt"))

    def test_memory_entries_have_stable_ids_and_can_be_edited(self):
        memory = UserMemory()
        memory.add_to("preferences", "Kısa cevapları severim", source="test")
        entry = memory.get_entries()[0]

        self.assertTrue(entry.get("id"))
        self.assertTrue(
            memory.update_entry(
                entry["id"], "preferences", "Orta uzunlukta cevapları severim"
            )
        )
        updated = memory.get_entries()[0]
        self.assertEqual(updated["id"], entry["id"])
        self.assertEqual(updated["value"], "Orta uzunlukta cevapları severim")
        self.assertEqual(updated["source"], "manual_edit")

    def test_memory_entry_can_be_removed_by_id(self):
        memory = UserMemory()
        memory.add_to("goals", "Python öğrenmek", source="test")
        entry_id = memory.get_entries()[0]["id"]

        self.assertTrue(memory.remove_by_id(entry_id))
        self.assertEqual(memory.get_entries(), [])
        self.assertFalse(memory.remove_by_id(entry_id))


class SecretRegressionTests(unittest.TestCase):
    def test_speech_listener_contains_no_embedded_google_key(self):
        source = Path("services/speech_listener.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("AIza", source)
        self.assertIn("GROQ_API_KEY", source)


class ForcedToolRoutingTests(unittest.TestCase):
    def test_explicit_file_delete_forces_real_tool(self):
        messages = [{
            "role": "user",
            "content": "masaüstümde heko.txt dosyasını sil",
        }]
        self.assertEqual(
            "delete_file",
            LLMClient._forced_tool_for_first_turn(messages),
        )

    def test_negative_delete_sentence_does_not_force_tool(self):
        messages = [{
            "role": "user",
            "content": "heko.txt dosyasını sakın silme",
        }]
        self.assertIsNone(
            LLMClient._forced_tool_for_first_turn(messages)
        )


if __name__ == "__main__":
    unittest.main()
