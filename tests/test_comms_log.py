from ui.comms_log import CommsLog


def test_append_tx(qapp_instance):
    log = CommsLog()
    log.append_entry("Tx", "P AA 45.0")
    assert log._table.rowCount() == 1
    assert log._table.item(0, 1).text() == "Tx"
    assert log._table.item(0, 2).text() == "P AA 45.0"


def test_append_rx(qapp_instance):
    log = CommsLog()
    log.append_entry("Rx", "OK")
    assert log._table.item(0, 1).text() == "Rx"


def test_clear(qapp_instance):
    log = CommsLog()
    log.append_entry("Tx", "P AA 45.0")
    log.append_entry("Rx", "OK")
    log.clear_log()
    assert log._table.rowCount() == 0
    assert log._entries == []


def test_entries_accumulate(qapp_instance):
    log = CommsLog()
    log.append_entry("Tx", "P AA 45.0")
    log.append_entry("Rx", "PA 45.0")
    assert len(log._entries) == 2
    assert log._entries[0][1] == "Tx"
    assert log._entries[1][1] == "Rx"
