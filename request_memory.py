import time
import socket
import struct
import random
import subprocess
from helpers import *
from entities import Entities

class CEServerClient:
    def __init__(self, host='127.0.0.1', port=52736):
        """Initialize client with default host and port, no connection yet."""
        self.host = host
        self.port = port
        self.socket = None
        self.process_handle = None

    def connect(self, pid):
        """Connect to server and open a process with given PID."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.socket.sendall(struct.pack('<BI', 3, pid))  # CMD_OPENPROCESS and PID
            self.process_handle = struct.unpack('<I', self.socket.recv(4))[0]
            print(f"Process Handler: {self.process_handle}")
        except Exception as e:
            print(f"Connection error: {e}")
            self.close()

    def read_memory_int(self, address, size_to_read=4, compress=0):
        """Read integer value from memory of connected process."""
        if not self.process_handle:
            print("Error: Connect to a process first.")
            return None
        try:
            data_to_send  = struct.pack('<B', 0x9)
            data_to_send  += struct.pack('<I', self.process_handle)
            data_to_send  += struct.pack('<Q', address)
            data_to_send  += struct.pack('<I', size_to_read)
            data_to_send  += struct.pack('<B', compress)
            self.socket.sendall(data_to_send)
            response = self.socket.recv(8)
            if len(response) >= 6:
                return struct.unpack_from('<i', response, 4)[0]
            else:
                #print("Incomplete server response.")
                return None
        except Exception as e:
            print(f"Read memory error: {e}")
            return None

    def read_memory_pt(self, address, size_to_read=80, compress=0):
        """Read integer value from memory of connected process."""
        if not self.process_handle:
            print("Error: Connect to a process first.")
            return None
        try:
            data_to_send  = struct.pack('<B', 0x9)
            data_to_send  += struct.pack('<I', self.process_handle)
            data_to_send  += struct.pack('<Q', address)
            data_to_send  += struct.pack('<I', size_to_read)
            data_to_send  += struct.pack('<B', compress)
            self.socket.sendall(data_to_send)
            response = self.socket.recv(4096)
            response_hex = response[4:10].hex()
            little_endian_hex = ''.join(reversed([response_hex[i:i+2] for i in range(0, len(response_hex), 2)]))
            return int(little_endian_hex,16)

        except Exception as e:
            #print(f"Read memory error: {e}")
            return None

    def create_toolhelp32_snapshot(self, dwFlags, th32ProcessID):
        """Create a snapshot of the process modules or threads."""
        try:
            self.socket.sendall(struct.pack('<BII', 35, dwFlags, th32ProcessID))
            data = self._receive_data()
            snapshot_modules = parse_response(data)
            return snapshot_modules
        except Exception as e:
            print(f"Snapshot creation error: {e}")

    def process32first(self, pid, handle=random.randint(1, 0x10000)):
        """Starts the enumeration of the processes."""
        # Including the handle (as an unsigned int) in the data packet to be sent.
        processname = "self".encode()
        processnamesize = len(processname)
        bytecode  = struct.pack('<B', 0x5)
        bytecode += struct.pack('<iii' + str(processnamesize) + "s", 1, pid, processnamesize, processname)
        self.socket.sendall(bytecode)
        response = self.socket.recv(1024)
        # Assuming you meant to return 'response' instead of 'data' as 'data' is not defined in your function.
        return response


    def process32next(self, pid):
        """Continues the enumeration of the processes."""
        try:
            # Including the handle (as an unsigned int) in the data packet to be sent.
            processname = "self".encode()
            processnamesize = len(processname)
            bytecode = struct.pack("<BIII", 0x6, 0, 0, 0)
            self.socket.sendall(bytecode)
            response = self.socket.recv(1024)
            hex_response = response.hex()
            formatted_hex = ' '.join(hex_response[i:i+8] for i in range(0, len(hex_response), 8))
            print(response)
            return response
        except Exception as e:
            print(f"Error continuing process enumeration: {e}")
            return None

    def _receive_data(self):
        """Internal method to receive data chunks from the server."""
        data = bytearray()
        while True:
            chunk = self.socket.recv(1024)
            if not chunk or len(chunk) < 1024:
                break
            data.extend(chunk)
        return data

    def _get_module_base_hex(self, snapshot_modules, module_name):
        # Iterate through each dictionary in the list
        for module in snapshot_modules:
            # Extract the actual module name from the 'modulename' field
            actual_module_name = module['modulename'].split('/')[-1]
            
            # Check if the input module_name matches the actual module name
            if actual_module_name == module_name:
                # Convert the modulebase to hex and return
                return hex(module['modulebase'])
        
        # Return this if no matching module name is found
        return "Module name not found in the list"

    def close(self):
        """Close the socket connection."""
        if self.socket:
            self.socket.close()
            self.socket = None

# Usage example
if __name__ == '__main__':
    ceserver_client = CEServerClient()
    
    command = 'adb shell "ps | grep com."'
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()
    pid = int(output.split()[1])

    ceserver_client.connect(pid)

    if ceserver_client.process_handle:
        snapshot_modules = ceserver_client.create_toolhelp32_snapshot(dwFlags=0x00000008, th32ProcessID=pid)
    print(snapshot_modules)
    libg_base_address = ceserver_client._get_module_base_hex(snapshot_modules, 'libg.so')
    libg_base_address = int(libg_base_address, 16)

    print("LIBG Base Address: ", hex(libg_base_address))
    print("Adding the offset: ", hex(libg_base_address + 0x00E25250))

    entities = Entities(ceserver_client)
    my_character = entities.read_me(libg_base_address)
    while True:
        start_time = time.time()  # Capture start time
        others_characters = entities.read_entities(libg_base_address)
        end_time = time.time()  # Capture end time after the function call

        # Calculate execution time in milliseconds
        execution_time_ms = (end_time - start_time) * 1000
        print(f"entities.read_entities execution time: {execution_time_ms} ms")

    """
    #ceserver_client._receive_data()
    for jump_character in range(0, 10*8, 8):
        offsets = [0x00E25250, jump_character, 0x10, 0x10, 0x60]
        print(offsets)
        pt = libg_base_address
        for offset in offsets[:-1]: 
            pt = ceserver_client.read_memory_pt(pt + offset)
            print(hex(pt))
        pt = ceserver_client.read_memory_int(pt + offsets[-1])
        print(pt)
    """
    """
    address_to_read = 0x7BD2B430FC60
    health = ceserver_client.read_memory_int(address_to_read)
    print(health)
    """
    ceserver_client.close()
