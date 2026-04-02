from ui.command_panel import CommandPanel


def test_instantiates(qapp_instance):
    assert CommandPanel() is not None


def test_disabled_by_default(qapp_instance):
    assert not CommandPanel()._scroll_content.isEnabled()


def test_set_enabled(qapp_instance):
    p = CommandPanel()
    p.set_enabled(True)
    assert p._scroll_content.isEnabled()


def test_manual_send_signal(qapp_instance):
    p = CommandPanel()
    p.set_enabled(True)
    received = []
    p.command_requested.connect(received.append)
    p._manual_field.setText("P RESET")
    p._on_manual_send()
    assert received == ["P RESET\r\n"]


def test_manual_send_clears_field(qapp_instance):
    p = CommandPanel()
    p.set_enabled(True)
    p._manual_field.setText("P RESET")
    p._on_manual_send()
    assert p._manual_field.text() == ""


def test_default_axis_pan(qapp_instance):
    assert CommandPanel()._axis() == "P"
