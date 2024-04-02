class Entities:
    def __init__(self, ceserver_client):
        self.ceserver_client = ceserver_client

    def read_me(self, libg_base_address):
        data = {}
        offsets = [0x00E25250, 0x0, 0x10, 0x10]
        pt = libg_base_address
        for offset in offsets: 
            pt = self.ceserver_client.read_memory_pt(pt + offset)
        # Read specific values after final address calculation
        return data


    def read_entities(self, libg_base_address):
        for jump_character in range(0, 10*8, 8):
            offsets = [0x00E25250, jump_character, 0x10, 0x10]
            pt = libg_base_address
            for offset in offsets: 
                pt = self.ceserver_client.read_memory_pt(pt + offset)
            if pt != None:
                health = self.ceserver_client.read_memory_int(pt + 0x60)
                if health != None:
                    data = {}
                    if data['is_enemy'] != 0:
                        data['is_enemy'] = 1
                        
                    print(data)
                else:
                    break
            else:
                break
