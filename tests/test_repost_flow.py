"""Tests for the video repost / separator flow in ``bot.handlers``.

These tests are skipped automatically when ``python-telegram-bot`` is not
installed, so ``python -m unittest discover -s tests`` stays green either way.

Run them with the project virtual environment::

    venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

try:  # pragma: no cover - depends on the environment
    from telegram import ChatMember
    from telegram.error import BadRequest

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
        ):
            self.id = 999
            self.calls = []
            self.copied_message_ids = []
            self._can_delete = can_delete
            self._copy_ok = copy_ok
            self._batch_copy_ok = batch_copy_ok
            self._fail_copy_ids = set(fail_copy_ids)
            self._delete_ok = delete_ok
            self._next_message_id = 500

        # -- test helpers ---------------------------------------------
        def call_names(self):
            """Names of the API methods called, in order."""
            return [name for name, _ in self.calls]

        # -- Telegram API ---------------------------------------------
        async def get_chat_member(self, chat_id, user_id):
            member = MagicMock()
            member.status = ChatMember.ADMINISTRATOR if self._can_delete else ChatMember.MEMBER
            member.can_delete_messages = self._can_delete
            return member

        async def send_message(self, chat_id, text):
            self.calls.append(("send_message", text))
            return MagicMock(message_id=len(self.calls))

        async def _make_copy(self):
            self._next_message_id += 1
            self.copied_message_ids.append(self._next_message_id)
            copy = MagicMock()
            copy.message_id = self._next_message_id
            return copy

        async def copy_message(self, chat_id, from_chat_id, message_id):
            self.calls.append(("copy_message", message_id))
            if not self._copy_ok or message_id in self._fail_copy_ids:
                raise BadRequest("Message to copy not found")
            return await self._make_copy()

        async def copy_messages(self, chat_id, from_chat_id, message_ids):
            self.calls.append(("copy_messages", tuple(message_ids)))
            if not self._copy_ok or not self._batch_copy_ok:
                raise BadRequest("Message to copy not found")
            return tuple([await self._make_copy() for _ in message_ids])

        async def delete_message(self, chat_id, message_id):
            self.calls.append(("delete_message", message_id))
            # Only the videos (never the bot's own reposts) can fail to be deleted.
            if not self._delete_ok and message_id not in self.copied_message_ids:
                raise BadRequest("Not enough rights to delete this message")
            return True

    class RepostFlowTestCase(unittest.IsolatedAsyncioTestCase):
        """Shared setup for the separator flow tests."""

        def setUp(self):
            handlers._chat_state.clear()
            self._mode_patch = patch.object(config, "bot_mode", "repost")
            self._mode_patch.start()
            self.addCleanup(self._mode_patch.stop)

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
