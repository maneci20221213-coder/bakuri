"""Single-instance IPC and native application bootstrap."""

import sys, json
from build_channel import DEVELOPMENT, SERVER_NAME
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .main_window import Window


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BakuriDevelopment")
    app.setQuitOnLastWindowClosed(False)
    if sys.platform == "win32" and not DEVELOPMENT:
        from windows import apply_install_options

        apply_install_options(sys.argv)
    from PySide6.QtNetwork import QLocalSocket, QLocalServer

    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    paths = sys.argv[sys.argv.index("--add-files") + 1 :] if "--add-files" in sys.argv else []
    if socket.waitForConnected(300):
        socket.write(
            json.dumps(
                {
                    "paths": paths,
                    "direct": "--background" not in sys.argv and "--add-files" not in sys.argv,
                }
            ).encode()
            + b"\n"
        )
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        sys.exit(0)
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    if not server.listen(SERVER_NAME):
        raise RuntimeError("다른 바꾸리가 실행 중입니다.")
    win = Window()
    clients = []

    def accept():
        while server.hasPendingConnections():
            client = server.nextPendingConnection()
            clients.append(client)
            client.buffer = b""

            def read(client=client):
                client.buffer += bytes(client.readAll())
                if b"\n" in client.buffer:
                    try:
                        payload = json.loads(client.buffer.split(b"\n", 1)[0])
                        direct = isinstance(payload, dict) and payload.get("direct", False)
                        received = (
                            payload.get("paths", []) if isinstance(payload, dict) else payload
                        )
                        if received:
                            win.files.add_paths(received)
                        if direct:
                            win.open_main("direct")
                        elif received:
                            win.show()
                            win.raise_()
                            win.activateWindow()
                    except (ValueError, TypeError):
                        pass
                    client.disconnectFromServer()

            def release(client=client):
                if client in clients:
                    clients.remove(client)
                client.deleteLater()

            client.disconnected.connect(release)
            client.readyRead.connect(read)
            read()

    server.newConnection.connect(accept)
    if paths:
        win.files.add_paths(paths)
    if "--background" not in sys.argv:
        win.show()
        if "--add-files" not in sys.argv:
            QTimer.singleShot(0, lambda: win.updater.request("direct"))
    sys.exit(app.exec())
