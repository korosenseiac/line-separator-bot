"""Tests for the video repost / separator flow in ``bot.handlers``.

These tests are skipped automatically when ``python-telegram-bot`` is not
installed, so ``python -m unittest discover -s tests`` stays green either way.

Run them with the project virtual environment::

    venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

try:  # pragma: no cover - depends on the environment
    from telegram import ChatMember
    from telegram.error import BadRequest, RetryAfter

    TELEGRAM_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency not installed
    TELEGRAM_AVAILABLE = False


if TELEGRAM_AVAILABLE:
    from bot import handlers
    from bot.config import config

    class FakeMessage:
        """Minimal stand-in for ``telegram.Message``."""

        def __init__(self, message_id, chat_id=-1000):
            self.message_id = message_id
            self.chat = MagicMock(id=chat_id)
            self.video = object()
            self.video_note = None
            self.animation = None
            self.document = None
            self.media_group_id = None

    class FakeBot:
        """Records every API call so tests can assert on their ordering."""

        def __init__(
            self,
            can_delete=True,
            copy_ok=True,
            batch_copy_ok=True,
            fail_copy_ids=(),
            delete_ok=True,
            flood_control_names=(),
            flood_control_ids=(),
            flood_control_times=1,
            retry_after=0,
        ):
            self.id = 999
            self.calls = []
            self.copied_message_ids = []
            self.flood_events = []
            self.retry_after = retry_after
            self._can_delete = can_delete
            self._copy_ok = copy_ok
            self._batch_copy_ok = batch_copy_ok
            self._fail_copy_ids = set(fail_copy_ids)
            self._delete_ok = delete_ok
            self._next_message_id = 500
            self._flood_names = {name: flood_control_times for name in flood_control_names}
            self._flood_ids = {message_id: flood_control_times for message_id in flood_control_ids}

        # -- test helpers ---------------------------------------------
        def _take_flood_hit(self, name, message_id=None):
            """Return True while this call must still answer with HTTP 429."""
            if message_id is not None and self._flood_ids.get(message_id, 0) > 0:
                self._flood_ids[message_id] -= 1
                self.flood_events.append((name, message_id))
                return True
            if self._flood_names.get(name, 0) > 0:
                self._flood_names[name] -= 1
                self.flood_events.append((name, message_id))
                return True
            return False

        def call_names(self):
            """Names of the API methods called, in order."""
            return [name for name, _ in self.calls]

        # -- Telegram API ---------------------------------------------
        async def get_chat_member(self, chat_id, user_id):
            self.calls.append(("get_chat_member", user_id))
            member = MagicMock()
            member.status = ChatMember.ADMINISTRATOR if self._can_delete else ChatMember.MEMBER
            member.can_delete_messages = self._can_delete
            return member

        async def send_message(self, chat_id, text):
            self.calls.append(("send_message", text))
            if self._take_flood_hit("send_message"):
                raise RetryAfter(self.retry_after)
            return MagicMock(message_id=len(self.calls))

        async def _make_copy(self):
            self._next_message_id += 1
            self.copied_message_ids.append(self._next_message_id)
            copy = MagicMock()
            copy.message_id = self._next_message_id
            return copy

        async def copy_message(self, chat_id, from_chat_id, message_id):
            self.calls.append(("copy_message", message_id))
            if self._take_flood_hit("copy_message", message_id):
                raise RetryAfter(self.retry_after)
            if not self._copy_ok or message_id in self._fail_copy_ids:
                raise BadRequest("Message to copy not found")
            return await self._make_copy()

        async def copy_messages(self, chat_id, from_chat_id, message_ids):
            self.calls.append(("copy_messages", tuple(message_ids)))
            if self._take_flood_hit("copy_messages"):
                raise RetryAfter(self.retry_after)
            if not self._copy_ok or not self._batch_copy_ok:
                raise BadRequest("Message to copy not found")
            return tuple([await self._make_copy() for _ in message_ids])

        async def delete_message(self, chat_id, message_id):
            self.calls.append(("delete_message", message_id))
            if self._take_flood_hit("delete_message", message_id):
                raise RetryAfter(self.retry_after)
            # Only the videos (never the bot's own reposts) can fail to be deleted.
            if not self._delete_ok and message_id not in self.copied_message_ids:
                raise BadRequest("Not enough rights to delete this message")
            return True

    class RepostFlowTestCase(unittest.IsolatedAsyncioTestCase):
        """Shared setup for the separator flow tests."""

        def setUp(self):
            handlers._chat_state.clear()
            handlers._flood_until.clear()
            handlers._last_call_at.clear()
            handlers._permission_cache.clear()
            self._mode_patch = patch.object(config, "bot_mode", "repost")
            self._mode_patch.start()
            self.addCleanup(self._mode_patch.stop)
            # Keep the tests fast and independent from any real .env values.
            for name, value in (
                ("flood_retry_max_attempts", 5),
                ("flood_retry_buffer_sec", 1.0),
                ("max_flood_wait_sec", 120.0),
                ("permission_cache_ttl_sec", 300.0),
                ("min_send_interval_sec", 0.0),
            ):
                patcher = patch.object(config, name, value)
                patcher.start()
                self.addCleanup(patcher.stop)

        def context_for(self, bot):
            return SimpleNamespace(bot=bot)

        def separator_lines(self, bot):
            return [payload for name, payload in bot.calls if name == "send_message"]

    class TestRepostSingleVideo(RepostFlowTestCase):
        """Repost mode for a standalone (forwarded or uploaded) video."""

        async def test_video_is_reposted_before_the_original_is_deleted(self):
            """Regression test.

            Deleting the original first made every repost fail ("message to copy
            not found"), leaving only separator lines with no video.
            """
            bot = FakeBot()

            await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))

            names = bot.call_names()
            self.assertIn("copy_message", names)
            self.assertIn("delete_message", names)
            self.assertLess(
                names.index("copy_message"),
                names.index("delete_message"),
                "The video must be reposted before its source message is deleted",
            )
            self.assertIn(("delete_message", 101), bot.calls)

            top, bottom = handlers.get_active_separators_for_chat(-1000)
            self.assertEqual(self.separator_lines(bot), [top, bottom])
            self.assertTrue(handlers.is_last_separator(-1000))

        async def test_original_video_is_never_deleted_when_the_repost_fails(self):
            bot = FakeBot(copy_ok=False)

            await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))

            self.assertNotIn("delete_message", bot.call_names())
            top, bottom = handlers.get_active_separators_for_chat(-1000)
            self.assertEqual(self.separator_lines(bot), [top, bottom])
            self.assertTrue(handlers.is_last_separator(-1000))

        async def test_reposted_copy_is_rolled_back_when_the_delete_is_refused(self):
            bot = FakeBot(delete_ok=False)

            await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))

            self.assertTrue(bot.copied_message_ids)
            for copied_id in bot.copied_message_ids:
                self.assertIn(("delete_message", copied_id), bot.calls)
            self.assertIn(("delete_message", 101), bot.calls)

        async def test_consecutive_videos_share_a_single_separator(self):
            bot = FakeBot()
            context = self.context_for(bot)

            await handlers.process_single_video(-1000, FakeMessage(101), context)
            await handlers.process_single_video(-1000, FakeMessage(102), context)

            top, bottom = handlers.get_active_separators_for_chat(-1000)
            self.assertEqual(self.separator_lines(bot), [top, bottom, bottom])
            self.assertEqual(bot.call_names().count("copy_message"), 2)

    class TestAppendFallback(RepostFlowTestCase):
        """The video must always survive, even when it cannot be reposted."""

        async def test_without_delete_permission_the_video_is_untouched(self):
            bot = FakeBot(can_delete=False)

            await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))

            self.assertNotIn("copy_message", bot.call_names())
            self.assertNotIn("delete_message", bot.call_names())
            _, bottom = handlers.get_active_separators_for_chat(-1000)
            self.assertEqual(self.separator_lines(bot), [bottom])
            self.assertTrue(handlers.is_last_separator(-1000))

        async def test_append_mode_never_touches_the_video(self):
            bot = FakeBot()

            with patch.object(config, "bot_mode", "append"):
                await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))

            self.assertNotIn("copy_message", bot.call_names())
            self.assertNotIn("delete_message", bot.call_names())
            self.assertEqual(len(self.separator_lines(bot)), 1)

    class TestMediaGroupRepost(RepostFlowTestCase):
        """Repost mode for albums (media groups)."""

        async def test_album_is_reposted_before_the_originals_are_deleted(self):
            bot = FakeBot()
            messages = [FakeMessage(201), FakeMessage(202)]

            await handlers.process_media_group(-1000, messages, self.context_for(bot))

            names = bot.call_names()
            self.assertIn("copy_messages", names)
            self.assertLess(
                names.index("copy_messages"),
                names.index("delete_message"),
                "The album must be reposted before its source messages are deleted",
            )
            self.assertIn(("delete_message", 201), bot.calls)
            self.assertIn(("delete_message", 202), bot.calls)
            top, bottom = handlers.get_active_separators_for_chat(-1000)
            self.assertEqual(self.separator_lines(bot), [top, bottom])

        async def test_incomplete_album_repost_keeps_the_originals(self):
            bot = FakeBot(batch_copy_ok=False, fail_copy_ids={202})
            messages = [FakeMessage(201), FakeMessage(202)]

            await handlers.process_media_group(-1000, messages, self.context_for(bot))

            self.assertNotIn(("delete_message", 201), bot.calls)
            self.assertNotIn(("delete_message", 202), bot.calls)
            self.assertTrue(bot.copied_message_ids)
            for copied_id in bot.copied_message_ids:
                self.assertIn(("delete_message", copied_id), bot.calls)

    class TestVideoDetection(unittest.TestCase):
        """Sanity checks for the message type detection."""

        def test_video_message_is_detected(self):
            self.assertTrue(handlers.is_video_message(FakeMessage(1)))

        def test_plain_text_message_is_ignored(self):
            text_message = MagicMock(video=None, video_note=None, animation=None, document=None)
            self.assertFalse(handlers.is_video_message(text_message))

    class TestFloodControl(RepostFlowTestCase):
        """Telegram flood control (HTTP 429) must be waited out, never dropped.

        Regression coverage for "forwarded 20 videos, the bot separated the first
        10 and then silently stopped": Telegram's per-group message limit answers
        with 429 + RetryAfter, which used to be logged and thrown away.
        """

        def flood_config(self, **overrides):
            """Use zero-second waits so the tests stay fast."""
            values = {
                "flood_retry_max_attempts": 3,
                "flood_retry_buffer_sec": 0.0,
                "max_flood_wait_sec": 120.0,
            }
            values.update(overrides)
            for name, value in values.items():
                patcher = patch.object(config, name, value)
                patcher.start()
                self.addCleanup(patcher.stop)

        async def test_flood_control_on_repost_is_waited_out_and_video_still_reposted(self):
            bot = FakeBot(flood_control_ids={101})
            self.flood_config()

            await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))

            # The 429 is retried instead of silently dropping the repost...
            self.assertEqual(bot.flood_events, [("copy_message", 101)])
            self.assertEqual(bot.call_names().count("copy_message"), 2)
            # ...so the whole flow still completes and the video survives.
            self.assertIn(("delete_message", 101), bot.calls)
            top, bottom = handlers.get_active_separators_for_chat(-1000)
            self.assertEqual(self.separator_lines(bot), [top, bottom])
            self.assertTrue(handlers.is_last_separator(-1000))

        async def test_flood_control_on_bottom_line_is_retried(self):
            bot = FakeBot(flood_control_names={"send_message"})
            self.flood_config()
            handlers.set_last_separator(-1000, True)  # bottom line only, no top line

            await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))

            self.assertEqual(bot.flood_events, [("send_message", None)])
            # Two attempts are recorded: the refused 429 and the successful retry.
            self.assertEqual(bot.call_names().count("send_message"), 2)
            self.assertTrue(handlers.is_last_separator(-1000))

        async def test_flood_wait_is_shared_by_the_following_calls(self):
            """After a 429 the closing line reuses the window instead of a 2nd 429."""
            bot = FakeBot(flood_control_ids={101}, retry_after=1)
            self.flood_config()
            handlers.set_last_separator(-1000, True)

            start = time.monotonic()
            await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))
            elapsed = time.monotonic() - start

            self.assertEqual(bot.flood_events, [("copy_message", 101)])
            self.assertEqual(bot.call_names().count("copy_message"), 2)
            self.assertGreaterEqual(elapsed, 1.0)  # the retry waited it out
            self.assertTrue(handlers.is_last_separator(-1000))

        async def test_flood_window_is_per_chat(self):
            """A flood window in one group must not delay another group."""
            handlers._flood_until[-1000] = time.monotonic() + 0.15

            start = time.monotonic()
            await handlers._await_flood_window(-2000)
            self.assertLess(time.monotonic() - start, 0.05)

            await handlers._await_flood_window(-1000)
            self.assertGreaterEqual(time.monotonic() - start, 0.1)

        async def test_persistent_flood_keeps_the_video(self):
            """When every retry is refused the original video is never deleted."""
            bot = FakeBot(flood_control_ids={101}, flood_control_times=5)
            self.flood_config(flood_retry_max_attempts=2)

            await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))

            self.assertEqual(bot.call_names().count("copy_message"), 2)
            self.assertNotIn("delete_message", bot.call_names())
            top, bottom = handlers.get_active_separators_for_chat(-1000)
            self.assertEqual(self.separator_lines(bot), [top, bottom])
            self.assertTrue(handlers.is_last_separator(-1000))

        async def test_absurd_flood_wait_gives_up_without_blocking_the_bot(self):
            bot = FakeBot(flood_control_ids={101}, retry_after=600)
            self.flood_config(max_flood_wait_sec=60)

            await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))

            self.assertEqual(bot.call_names().count("copy_message"), 1)
            self.assertNotIn("delete_message", bot.call_names())
            # The video is kept and only the closing line is added.
            top, bottom = handlers.get_active_separators_for_chat(-1000)
            self.assertEqual(self.separator_lines(bot), [top, bottom])

        async def test_album_repost_survives_flood_control(self):
            bot = FakeBot(flood_control_names={"copy_messages"})
            self.flood_config()

            messages = [FakeMessage(201), FakeMessage(202)]
            await handlers.process_media_group(-1000, messages, self.context_for(bot))

            self.assertEqual(bot.flood_events, [("copy_messages", None)])
            self.assertEqual(bot.call_names().count("copy_messages"), 2)
            self.assertIn(("delete_message", 201), bot.calls)
            self.assertIn(("delete_message", 202), bot.calls)

    class TestApiCallThrottling(RepostFlowTestCase):
        """Permission caching and proactive send pacing reduce API pressure."""

        async def test_permission_lookup_is_cached_per_chat(self):
            bot = FakeBot()

            await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))
            await handlers.process_single_video(-1000, FakeMessage(102), self.context_for(bot))

            self.assertEqual(bot.call_names().count("get_chat_member"), 1)

        async def test_permission_cache_can_be_disabled(self):
            bot = FakeBot()

            with patch.object(config, "permission_cache_ttl_sec", 0):
                await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))
                await handlers.process_single_video(-1000, FakeMessage(102), self.context_for(bot))

            self.assertEqual(bot.call_names().count("get_chat_member"), 2)

        async def test_permission_lookup_is_not_paced_like_a_message(self):
            bot = FakeBot()

            with patch.object(config, "min_send_interval_sec", 0.2), patch.object(
                config, "permission_cache_ttl_sec", 0
            ):
                handlers._last_call_at[-1000] = time.monotonic()
                start = time.monotonic()
                can_delete = await handlers._can_delete_messages(-1000, self.context_for(bot))
                elapsed = time.monotonic() - start

            self.assertTrue(can_delete)
            self.assertLess(elapsed, 0.1)

        async def test_send_pacing_spaces_out_messages(self):
            bot = FakeBot()

            with patch.object(config, "min_send_interval_sec", 0.05):
                start = time.monotonic()
                await handlers.process_single_video(-1000, FakeMessage(101), self.context_for(bot))
                elapsed = time.monotonic() - start

            # Top line, repost and bottom line are paced -> at least two gaps.
            self.assertGreaterEqual(elapsed, 0.1)
            top, bottom = handlers.get_active_separators_for_chat(-1000)
            self.assertEqual(self.separator_lines(bot), [top, bottom])
