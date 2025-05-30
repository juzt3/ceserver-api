from socket import socket, AF_INET, SOCK_STREAM
import struct
import logging

from commands import CeserverCommand as CE_CMD
from structs import CeVersion, CeProcessEntry, CeReadProcessMemoryInput
from data_classes import ProcessInfo


class CEServerClient:
    def __init__(self, host='127.0.0.1', port=52736):
        self.log = logging.getLogger(__name__)
        self._sock: socket | None = None
        self.host: str = host
        self.port: int = port
        self.pid: int | None = None
        self.handle: int | None = None

        logging.basicConfig(
            format='%(asctime)s %(levelname)-8s %(message)s',
            level=logging.INFO,
            datefmt='%Y-%m-%d %H:%M:%S')

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def _send_command(self, command: CE_CMD, payload=b''):
        self._sock.sendall(command.to_bytes() + payload)

    def connect(self):
        self._sock = socket(AF_INET, SOCK_STREAM)
        self._sock.settimeout(2)
        self._sock.connect((self.host, self.port))
        self.log.info(f"Connected to ceserver in {self.host}:{self.port}")
        self.get_version()

    def get_version(self):
        self._send_command(CE_CMD.CMD_GETVERSION)
        data = self._sock.recv(CeVersion.sizeof())
        ce_version = CeVersion.parse(data)
        version_string = self._sock.recv(ce_version.stringsize)
        self.log.info(f"Server version: {version_string.decode()}")

    def is_android(self) -> bool:
        self._send_command(CE_CMD.CMD_ISANDROID)
        data = self._sock.recv(1)
        return bool(data[0])

    def disconnect(self):
        self._send_command(CE_CMD.CMD_CLOSECONNECTION)
        self._sock.close()
        self.log.info("Disconnected.")

    def enumerate_processes(self) -> list[ProcessInfo]:
        # Paso 1: snapshot
        self._send_command(CE_CMD.CMD_CREATETOOLHELP32SNAPSHOTEX, b"\x02\x00\x00\x00\x00\x00\x00\x00")
        snapshot_handle = self._sock.recv(4)
        processes = []
        # next process
        self._sock.sendall(CE_CMD.CMD_PROCESS32FIRST.to_bytes() + snapshot_handle)
        ce_process_entry = self._recv_process_entry()
        if ce_process_entry.result:
            process_name = self._sock.recv(ce_process_entry.processnamesize)
            processes.append(ProcessInfo(ce_process_entry.pid, process_name.decode()))
            while ce_process_entry.result:
                self._sock.sendall(CE_CMD.CMD_PROCESS32NEXT.to_bytes() + snapshot_handle)
                ce_process_entry = self._recv_process_entry()
                if ce_process_entry.result:
                    process_name = self._sock.recv(ce_process_entry.processnamesize)
                    processes.append(ProcessInfo(ce_process_entry.pid, process_name.decode()))
        self.close_handle(snapshot_handle)

        return processes

    def _recv_process_entry(self) -> CeProcessEntry:
        data = self._sock.recv(CeProcessEntry.sizeof())
        ce_process_entry = CeProcessEntry.parse(data)
        return ce_process_entry

    def close_handle(self, handle: bytes):
        self._sock.sendall(CE_CMD.CMD_CLOSEHANDLE.to_bytes() + handle)
        self._sock.recv(4)

    def get_handle(self, process_name: str):
        processes_list = self.enumerate_processes()
        for process_info in processes_list:
            name = process_info.name
            pid = process_info.pid
            if process_name in name:
                self.pid = pid
                self.open_process()
                self.log.info(f"Process found: {pid}-{name}")
                return
        raise Exception("Process not found.")

    def open_process(self):
        self._send_command(CE_CMD.CMD_OPENPROCESS, self.pid.to_bytes(4, byteorder='little'))
        self.handle = struct.unpack("<L", self._sock.recv(4))[0]

    def read_process_memory(self, address: int, size: int, compress: int = 0) -> bytes | None:
        data = {
            "handle": self.handle,
            "address": address,
            "size": size,
            "compress": compress
        }

        payload = CeReadProcessMemoryInput.build(data)
        self._send_command(CE_CMD.CMD_READPROCESSMEMORY, payload)
        value = self._recv_read_response()
        return value

    def _recv_read_response(self) -> bytes | None:
        response_size = struct.unpack("<L", self._sock.recv(4))[0]
        if response_size == 0:
            return
        value = self._sock.recv(response_size)
        return value

    def read_byte(self, address: int, compress: int = 0) -> int | None:
        data = self.read_process_memory(address, 1, compress)
        if data is None:
            return None
        return struct.unpack('<B', data)[0]

    def read_int16(self, address: int, compress: int = 0, signed: bool = True) -> int | None:
        data = self.read_process_memory(address, 2, compress)
        if data is None:
            return None
        fmt = "<h" if signed else "<H"
        return struct.unpack(fmt, data)[0]

    def read_uint16(self, address: int, compress: int = 0) -> int | None:
        return self.read_int16(address, compress, False)

    def read_int32(self, address: int, compress: int = 0, signed: bool = True) -> int | None:
        value = self.read_process_memory(address, 4, compress)
        if value is None:
            return None
        fmt = "<l" if signed else "<L"
        return struct.unpack(fmt, value)[0]

    def read_uint32(self, address: int, compress: int = 0) -> int | None:
        return self.read_int32(address, compress, False)

    def read_int64(self, address: int, compress: int = 0, signed: bool = True) -> int | None:
        value = self.read_process_memory(address, 8, compress)
        if value is None:
            return None
        fmt = "<q" if signed else "<Q"
        return struct.unpack(fmt, value)[0]

    def read_uint64(self, address: int, compress: int = 0) -> int | None:
        return self.read_int64(address, compress, False)

    def read_float(self, address: int, compress: int = 0) -> float | None:
        value = self.read_process_memory(address, 4, compress)
        if value is None:
            return None
        return struct.unpack("<f", value)[0]

    def read_double(self, address: int, compress: int = 0) -> float | None:
        value = self.read_process_memory(address, 8, compress)
        if value is None:
            return None
        return struct.unpack("<d", value)[0]

    def read_bytes(self, address: int, length: int, compress: int = 0):
        return self.read_process_memory(address, length, compress)

    def read_str(self, address: int, length: int = 256, unicode=False, compress: int = 0) -> str | None:
        data = self.read_bytes(address, length, compress)
        if data is None:
            return None

        try:
            string_bytes = data.split(b'\x00', 1)[0]  # cortar en nulo si existe
            encoding = "utf-16" if unicode else "utf-8"
            return string_bytes.decode(encoding, errors='ignore')
        except Exception as e:
            self.log.error(f"[!] Error decoding string: {e}")
            return None

    def read_ptr(self, address: int, compress: int = 0) -> int | None:
        ptr = self.read_uint64(address, compress)
        MIN_ADDR = 0x10000
        # Likely an invalid pointer
        if ptr is None or ptr < MIN_ADDR:
            return None
        return ptr

    def read_pointer_chain(self, base: int, offsets: list[int], compress: int = 0) -> int | None:
        addr = base
        for off in offsets:
            ptr = self.read_ptr(addr + off, compress)
            if ptr is None:
                return None
            addr = ptr
        return addr
