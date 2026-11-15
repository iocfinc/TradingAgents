from cli import utils


def test_openrouter_selector_prioritizes_hy3_preview(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        utils,
        "_fetch_openrouter_models",
        lambda: [
            ("DeepSeek V4 Pro", "deepseek/deepseek-v4-pro"),
            ("Tencent HY3 Preview", "tencent/hy3-preview"),
            ("Kimi K2.6", "moonshotai/kimi-k2.6"),
        ],
    )

    def fake_select(*args, **kwargs):
        captured["choices"] = kwargs["choices"]

        class Prompt:
            def ask(self_nonlocal):
                return "tencent/hy3-preview"

        return Prompt()

    monkeypatch.setattr(utils.questionary, "select", fake_select)

    selected = utils.select_openrouter_model()

    assert selected == "tencent/hy3-preview"
    assert captured["choices"][0].value == "tencent/hy3-preview"


def test_openrouter_selector_falls_back_to_hy3_preview_when_catalog_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(utils, "_fetch_openrouter_models", lambda: [])

    def fake_select(*args, **kwargs):
        choices = kwargs["choices"]

        class Prompt:
            def ask(self_nonlocal):
                return choices[0].value

        return Prompt()

    monkeypatch.setattr(utils.questionary, "select", fake_select)

    selected = utils.select_openrouter_model()

    assert selected == "tencent/hy3-preview"
