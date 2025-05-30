from socket import socket, AF_INET, SOCK_STREAM
from commands import CESERVER_COMMAND as CE_CMD
from structs import CeVersion, CeProcessEntry, CeReadProcessMemoryInput
import struct


class CEServerClient:
    def __init__(self, host='127.0.0.1', port=52736):
        self.host: str = host
        self.port: int = port
        self.sock: socket | None = None
        self.pid: int | None = None
        self.handle: int | None = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def send_command(self, command: CE_CMD, payload=b''):
        self.sock.sendall(command.to_bytes()+payload)

    def connect(self):
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.settimeout(0.1)
        self.sock.connect((self.host, self.port))
        print(f"[+] Connected to ceserver in {self.host}:{self.port}")
        self.get_version()

    def get_version(self):
        self.send_command(CE_CMD.CMD_GETVERSION)
        data = self.sock.recv(CeVersion.sizeof())
        ce_version = CeVersion.parse(data)
        versionstring = self.sock.recv(ce_version.stringsize)
        print(f"[+] Server version: {versionstring.decode()}")

    def disconnect(self):
        self.send_command(CE_CMD.CMD_CLOSECONNECTION)
        self.sock.close()
        print("[+] Disconnected.")

    def enumerate_processes(self):
        # Paso 1: snapshot
        self.sock.sendall(CE_CMD.CMD_CREATETOOLHELP32SNAPSHOTEX.to_bytes()+b"\x02\x00\x00\x00\x00\x00\x00\x00")
        handle = self.sock.recv(4)
        processes = []
        # next process
        self.sock.sendall(CE_CMD.CMD_PROCESS32FIRST.to_bytes()+handle)
        data = self.sock.recv(CeProcessEntry.sizeof())
        ce_process_entry = CeProcessEntry.parse(data)
        if ce_process_entry.result:
            process_name = self.sock.recv(ce_process_entry.processnamesize)
            processes.append((ce_process_entry.pid, process_name.decode()))
            while ce_process_entry.result:
                self.sock.sendall(CE_CMD.CMD_PROCESS32NEXT.to_bytes()+handle)
                data = self.sock.recv(CeProcessEntry.sizeof())
                ce_process_entry = CeProcessEntry.parse(data)
                if ce_process_entry.result:
                    process_name = self.sock.recv(ce_process_entry.processnamesize)
                    processes.append((ce_process_entry.pid, process_name.decode()))
        self.close_handle(handle)

        return processes

    def close_handle(self, handle: bytes):
        self.sock.sendall(CE_CMD.CMD_CLOSEHANDLE.to_bytes() + handle)
        self.sock.recv(4)

    def get_handle(self, process_name: str):
        processes_list = self.enumerate_processes()
        for pid, name in processes_list:
            if process_name in name:
                self.pid = pid
                self.open_process()
                print(f"Process found: {pid}-{name}")
                return
        raise Exception("Process not found.")

    def open_process(self):
        self.send_command(CE_CMD.CMD_OPENPROCESS, self.pid.to_bytes(4, byteorder='little'))
        self.handle = struct.unpack("<L", self.sock.recv(4))[0]

    def read_process_memory(self, address: int, size: int, compress:int = 0) -> bytes | None:
        data = {
            "handle": self.handle,
            "address": address,
            "size": size,
            "compress": compress
        }

        payload = CeReadProcessMemoryInput.build(data)
        self.send_command(CE_CMD.CMD_READPROCESSMEMORY, payload)
        response_size = struct.unpack("<L", self.sock.recv(4))[0]
        if response_size == 0:
            return
        value = self.sock.recv(response_size)
        return value

    def read_int32(self, address: int, compress: int = 0) -> int | None:
        value = self.read_process_memory(address, 4, compress)
        if value is None:
            return None
        return struct.unpack("<L", value)[0]

    def read_float(self, address: int, compress: int = 0) -> float | None:
        value = self.read_process_memory(address, 4, compress)
        if value is None:
            return None
        return struct.unpack("<f", value)[0]
