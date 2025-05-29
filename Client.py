import socket
import struct
from construct import Struct, Int32ul
from ceservercommand import CESERVER_COMMAND as CE_CMD


CEServerPacketHeader = Struct(
    "command" / Int32ul,
    "size" / Int32ul
)


class CEServerClient:
    def __init__(self, host='127.0.0.1', port=52736):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None

    def send_command(self, command: CE_CMD):
        self.sock.sendall(command.to_bytes())

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(0.1)
        self.sock.connect((self.host, self.port))
        print(f"[+] Conectado a ceserver en {self.host}:{self.port}")
        self.get_version()

    def get_version(self):
        self.send_command(CE_CMD.CMD_GETVERSION)
        data = self.sock.recv(5)
        version, stringsize = struct.unpack('>IB', data)
        versionstring = self.sock.recv(stringsize)
        print(f"[+] Versión del servidor: {versionstring.decode()}")

    def disconnect(self):
        self.send_command(CE_CMD.CMD_CLOSECONNECTION)
        self.sock.close()
        print("[+] Desconectado.")

    def enumerate_processes(self):
        # Paso 1: snapshot
        self.sock.sendall(b"\x23\x02\x00\x00\x00\x00\x00\x00\x00")
        key = self.sock.recv(4)
        # next process
        self.sock.sendall(CE_CMD.CMD_PROCESS32FIRST.to_bytes()+key)
        data = self.sock.recv(12)
        result, pid, process_name_size = struct.unpack('>III', data)
        if result:
            process_name = self.sock.recv(process_name_size)
            print(process_name.decode())
            while result:
                self.sock.sendall(CE_CMD.CMD_PROCESS32NEXT.to_bytes()+key)
                data = self.sock.recv(12)
                result, pid, process_name_size = struct.unpack('>III', data)
                if result:
                    process_name = self.sock.recv(process_name_size)
                    print(process_name.decode())
        self.sock.sendall(CE_CMD.CMD_CLOSEHANDLE.to_bytes() + key)
        self.sock.recv(4)


# Prueba
if __name__ == "__main__":
    client = CEServerClient("172.20.24.24")  # IP de ceserver
    try:
        client.connect()
        client.enumerate_processes()
    finally:
        client.disconnect()
