from app import promoter_role_progress as progress


def test_progress_estimate_uses_only_new_successes():
    message = progress.format_progress(progress.Progress(100, 20, 3), progress.Progress(100, 30, 2), "quota")
    assert "До прохода: 20 из 100" in message
    assert "Обработано за проход: 10" in message
    assert "Готово всего: 30 из 100 (30.0%)" in message
    assert "Осталось: 70; из них ошибок: 2" in message
    assert "около 7" in message


def test_no_progress_does_not_invent_estimate():
    snapshot = progress.Progress(100, 20, 3)
    assert "пока нельзя оценить" in progress.format_progress(snapshot, snapshot, "quota")


def test_sends_to_configured_chats_without_exposing_token(monkeypatch):
    calls = []

    class Bot:
        def __init__(self, token):
            assert token == "test-token"

        def send(self, message, *, chat_id):
            calls.append((message, chat_id))

    monkeypatch.setenv("SUPERVISOR_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("SUPERVISOR_TELEGRAM_CHAT_IDS", "123, 456")
    monkeypatch.setattr(progress, "TelegramBotApi", Bot)
    progress.notify_progress("hello")
    assert calls == [("hello", "123"), ("hello", "456")]
