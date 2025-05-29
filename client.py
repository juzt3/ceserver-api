import socket
from commands import CESERVER_COMMAND as CE_CMD
from structs import CeVersion, CeProcessEntry, CeVirtualQueryExFullInput


class CEServerClient:
    def __init__(self, host='127.0.0.1', port=52736):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.handle = None

    def send_command(self, command: CE_CMD, payload=b''):
        self.sock.sendall(command.to_bytes()+payload)

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(0.1)
        self.sock.connect((self.host, self.port))
        print(f"[+] Conectado a ceserver en {self.host}:{self.port}")
        self.get_version()

    def get_version(self):
        self.send_command(CE_CMD.CMD_GETVERSION)
        data = self.sock.recv(CeVersion.sizeof())
        ce_version = CeVersion.parse(data)
        versionstring = self.sock.recv(ce_version.stringsize)
        print(f"[+] Versión del servidor: {versionstring.decode()}")

    def disconnect(self):
        self.send_command(CE_CMD.CMD_CLOSECONNECTION)
        self.sock.close()
        print("[+] Desconectado.")

    def enumerate_processes(self):
        # Paso 1: snapshot
        self.sock.sendall(CE_CMD.CMD_CREATETOOLHELP32SNAPSHOTEX.to_bytes()+b"\x02\x00\x00\x00\x00\x00\x00\x00")
        key = self.sock.recv(4)
        processes = []
        # next process
        self.sock.sendall(CE_CMD.CMD_PROCESS32FIRST.to_bytes()+key)
        data = self.sock.recv(CeProcessEntry.sizeof())
        ce_process_entry = CeProcessEntry.parse(data)
        if ce_process_entry.result:
            process_name = self.sock.recv(ce_process_entry.processnamesize)
            processes.append((ce_process_entry.pid, process_name.decode()))
            while ce_process_entry.result:
                self.sock.sendall(CE_CMD.CMD_PROCESS32NEXT.to_bytes()+key)
                data = self.sock.recv(CeProcessEntry.sizeof())
                ce_process_entry = CeProcessEntry.parse(data)
                if ce_process_entry.result:
                    process_name = self.sock.recv(ce_process_entry.processnamesize)
                    processes.append((ce_process_entry.pid, process_name.decode()))
        self.sock.sendall(CE_CMD.CMD_CLOSEHANDLE.to_bytes() + key)
        self.sock.recv(4)

        return processes

    def get_handle(self, process_name):
        processes_list = self.enumerate_processes()
        for pid, name in processes_list:
            if process_name in name:
                self.handle = pid.to_bytes(4, byteorder='little')
                print(f"{pid}-{name}")
                break

    def open_process(self):
        self.send_command(CE_CMD.CMD_OPENPROCESS, self.handle)
        self.sock.recv(4)
