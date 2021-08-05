import socket
from helper import PacketDecoder, PacketEncoder
from collections import OrderedDict
from datetime import datetime
import sys

class Receiver():
    def __init__(self, port, file_name) -> None:
        self.port = port
        self.filename = file_name
        
        # initialize variables
        self.seqNo = 0   # ISN set to 0
        self.ackNo = 0   # ackNo set to 0
        self.mss = 1024  # mss is the same as the mss in the sender + header size
        self.buffer = OrderedDict()  # create a buffer
        self.data_amount = 0
        self.seg_amount = 0
        self.dup_seg = 0
        # clear up Receiver log
        try:
            f = open('Receiver_log.txt', 'x')
        except:
            f = open('Receiver_log.txt', 'w')
            f.write('')
        f.close()
        pass
        # write the data segments in the buffer to the file

    def write_buffer(self):
        buffer = self.buffer
        dup_seg = self.dup_seg
        # create the file, or clean up the file if it exists
        try:
            f = open(self.filename, 'x')
        except:
            f = open(self.filename, 'w')
            f.write('')
        f.close()

        # write the buffer chunks to the file
        f = open(self.filename, 'w')
        for k, v in buffer.items():
            f.seek(k-1)
            f.write(v)
        f.close()

        f = open(self.filename, 'r')
        data_amount = len(f.read())
        seg_amount = len(buffer)
        f.close()

        f = open('Receiver_log.txt', 'a')
        f.write('\n')
        f.write('Amount of (original) Data Received (in bytes): %d\n' % data_amount)
        f.write('Number of (original) Data Segments Received: %d\n' % seg_amount)
        f.write('Number of duplicate segments received (if any): %d\n' % dup_seg)
        f.close()
        


    # write the log to Receiver_log.txt
    def write_log(self, action, type_of_packet, seqNo, numBytes, ackNo):
        action = str(action).ljust(5)
        time_point = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3] + ' '
        type_of_packet = str(type_of_packet).ljust(3)
        seqNo = str(seqNo).ljust(7)
        numBytes = str(numBytes).ljust(6)
        ackNo = str(ackNo) + ' '
        log = ''.join([action, time_point, type_of_packet, seqNo, numBytes, ackNo])+'\n'

        f = open('Receiver_log.txt', 'a')
        f.write(log)
        f.close()
        pass

    def get_ack(self):
        i = self.ackNo
        while True:
            if i not in self.buffer:
                break
            i += self.mss
        return i

    def check_ack(self, recv_seqNo):
        for i in range(self.ackNo, recv_seqNo, self.mss):
            if i not in self.buffer:
                return False
        return True

    def receive(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(('127.0.0.1', self.port))

        write_log = self.write_log
        write_buffer = self.write_buffer
        check_ack = self.check_ack

        while True:
            data, addr = s.recvfrom(self.mss+16)
            data = PacketDecoder(data).get_packet()

            ptype = data['ptype']

            write_log('recv', ptype, data['seqNo'], len(data['data']), data['ackNo'])

            if ptype == 'S' or ptype == 'F':
                self.ackNo = data['seqNo'] + 1
                ptype = data['ptype'] + 'A'
                response = PacketEncoder(seqNo=self.seqNo, ptype=ptype, data=b'', mss=self.mss, ackNo=self.ackNo).encode_packet()
                s.sendto(response, addr)
                write_log('snd', ptype, self.seqNo, 0, self.ackNo)
            elif ptype == 'A':
                if self.buffer:
                    write_buffer()
                    self.seqNo = 0   # ISN set to 0
                    self.ackNo = 0   # ackNo set to 0
                    break
                else:
                    self.mss = data['mss']
            else:
                ptype = data['ptype']

                # if the seqNo of received data not in buffer, push it to the buffer
                if not data['seqNo'] in self.buffer:
                    self.buffer.update(dict([(data['seqNo'], data['data'])]))
                else:
                    self.dup_seg += 1
                
                # check if all the data prior to seqNo is recevied
                if check_ack(data['seqNo']):
                    # if all data prior to seqNo is received, ackNo is the next one
                    self.ackNo = data['seqNo'] + len(data['data'])

                seqNo = data['ackNo']
                response = PacketEncoder(seqNo=self.seqNo, ptype=ptype, data=b'', mss=self.mss, ackNo=self.ackNo).encode_packet()
                s.sendto(response, addr)
                write_log('snd', 'A', self.seqNo, 0, self.ackNo)
        pass
    
if __name__ == '__main__':
    args = sys.argv
    arg_size = len(args)
    receiver_port = int(args[1]) if arg_size > 1 else 8000
    file_name = args[2] if arg_size > 2 else "FileReceived.txt"
    r = Receiver(receiver_port, file_name)
    r.receive()