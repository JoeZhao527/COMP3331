import time

class PacketDecoder:
    def __init__(self, packet):
        src = packet[0:2]
        self.src = int.from_bytes(src, 'big')

        dest = packet[2:4]
        self.dest = int.from_bytes(dest, 'big')

        seqNo = packet[4:8]
        self.seqNo = int.from_bytes(seqNo, 'big')

        ackNo = packet[8:12]
        self.ackNo = int.from_bytes(ackNo, 'big')

        ptype = packet[12:14]
        self.ptype = self.int_to_ptype(int.from_bytes(ptype, 'big'))

        self.mss = int.from_bytes(packet[14:16], 'big')
        self.data = packet[16:].decode()
    
    def int_to_ptype(self, n):
        return {
            1: 'S', 2: 'A', 3: 'SA',
            4: 'F', 6: 'FA', 8: 'D'
        }[n]

    def get_packet(self):
        return {
            'src': self.src,
            'dest': self.dest,
            'seqNo': self.seqNo,
            'ackNo': self.ackNo,
            'ptype': self.ptype,
            'mss': self.mss,
            'data': self.data
        }

class PacketEncoder:
    def __init__(self, seqNo, ptype, data=b'', mss=1, ackNo=0, src=8000, dest=8000) -> None:
        self.src = src
        self.dest = dest
        self.seqNo = seqNo
        self.ackNo = ackNo
        self.ptype = ptype
        self.mss = mss
        self.data = data
        pass

    def encode_packet(self):
        return self.encode_header() + self.data

    ''' Header
    0                2                4
    +----------------+----------------+
    |   source port  |   dest port    |
    +----------------+----------------+
    |         sequence number         |
    +----------------+----------------+
    |           ACK  number           |
    +---+---+---+----+----------------+
    | S | A | F | D  |max segment size|
    +---+---+---+----+----------------+
    '''
    # generate header field, should includes:
    #   1. source port
    #   2. destination port
    #   3. sequence number
    #   4. type of packet, could be S(SYN), A(ACK), F(FIN), D(DATA)
    # return value: a 12-bytes header
    def encode_header(self):
        src_port = self.src
        src = src_port.to_bytes(2, 'big')
        dest_port = self.dest
        dest = dest_port.to_bytes(2, 'big')

        pt = self.ptype_to_int().to_bytes(2, 'big')

        seq = self.seqNo.to_bytes(4, 'big')
        ack = self.ackNo.to_bytes(4, 'big')


        mss = self.mss.to_bytes(2, 'big')

        return src + dest + seq + ack + pt + mss

    # convert ptype to an unique integer
    def ptype_to_int(self):
        res = 0
        for c in self.ptype:
            res += 1 if c == 'S' else 0
            res += 2 if c == 'A' else 0
            res += 4 if c == 'F' else 0
            res += 8 if c == 'D' else 0
        return res