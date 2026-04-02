from ui.main_window import MainWindow


def test_instantiates(qapp_instance):
    assert MainWindow().windowTitle() == "Jasmine Debugger"


def test_initial_credentials(qapp_instance):
    w = MainWindow()
    assert w._ip_field.text() == "192.168.1.100"
    assert w._user_field.text() == "silentsentinel"


def test_disconnect_disabled_initially(qapp_instance):
    w = MainWindow()
    assert not w._btn_disconnect.isEnabled()
    assert w._btn_connect.isEnabled()


def test_status_label_initial(qapp_instance):
    assert MainWindow()._status_label.text() == "Disconnected"
