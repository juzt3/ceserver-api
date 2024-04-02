def parse_response(response):
    # Helper function to format and split hex data
    def format_and_split(hex_str):
        return [hex_str[i:i+2] for i in range(0, len(hex_str), 2)]

    # Split the response into parts for each module entry
    parts = response.split(b'.so')
    module_entries = []

    for part in parts[:-1]:  # Ignore the last part if it's not a module
        entry_info = part + b'.so'
        start_index = entry_info.rfind(b'\x00') + 1
        # Decode the library name
        library_name = entry_info[start_index:].decode('utf-8')
        # Extract the hex data for parsing
        hex_data = entry_info[:start_index].hex()
        # Splitting hex data into bytes for easier manipulation
        hex_bytes = format_and_split(hex_data)

        # Assuming the structure is at the beginning of each entry
        result = int.from_bytes(bytes.fromhex(''.join(hex_bytes[:4])), byteorder='little', signed=True)
        modulebase = int.from_bytes(bytes.fromhex(''.join(hex_bytes[4:12])), byteorder='little', signed=False)
        modulepart = int.from_bytes(bytes.fromhex(''.join(hex_bytes[12:16])), byteorder='little', signed=True)
        modulesize = int.from_bytes(bytes.fromhex(''.join(hex_bytes[16:20])), byteorder='little', signed=True)
        modulefileoffset = int.from_bytes(bytes.fromhex(''.join(hex_bytes[20:24])), byteorder='little', signed=False)
        modulenamesize = int.from_bytes(bytes.fromhex(''.join(hex_bytes[24:28])), byteorder='little', signed=True)

        # Append the parsed module entry to the list
        module_entries.append({
            'result': result,
            'modulebase': modulebase,
            'modulepart': modulepart,
            'modulesize': modulesize,
            'modulefileoffset': modulefileoffset,
            'modulenamesize': modulenamesize,
            'modulename': library_name
        })

    return module_entries