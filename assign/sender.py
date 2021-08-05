from helper import PacketDecoder
from helper import PacketEncoder
import socket
import sys
import random
import math
from datetime import datetime, time, timedelta

class Sender(object):
    def __init__(self, dest_ip, dest_port, file, mws, mss, timeout, pdrop, seed):
        # sender log data variables
        self.data_amount = 0 # Amount of (original) Data Transferred (in bytes)
        self.seg_num = 0 # Number of Data Segments Sent (excluding retransmissions)
        self.drop_num = 0 # Number of (all) Packets Dropped (by the PL module)
        self.total_seg_num = 0 # Number of Retransmitted Segments
        self.dup_ack_num = 0 # Number of Duplicate Acknowledgements received

        # sender informations
        self.dest_ip = dest_ip
        self.dest_port = dest_port
        self.mss = mss
        self.mws = mws
        self.data = self.read_file(file)
        self.timeout = timeout
        self.seqNo = 0
        self.pl = PacketLoss(pdrop, seed)

        self.last_send = 1
        self.total_time = 0
        # clear up sender log
        try:
            f = open('Sender_log.txt', 'x')
        except:
            f = open('Sender_log.txt', 'w')
            f.write('')
        f.close()


    # read the txt file to a byte string
    def read_file(self, file):
        f = open(file, "r")
        txt = f.read()
        f.close()
        return txt

    def write_log(self, action, type_of_packet, seqNo, numBytes, ackNo):
        action = str(action).ljust(5)
        time_point = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3] + ' '
        type_of_packet = str(type_of_packet).ljust(3)
        seqNo = str(seqNo).ljust(7)
        numBytes = str(numBytes).ljust(6)
        ackNo = str(ackNo) + ' '
        log = ''.join([action, time_point, type_of_packet, seqNo, numBytes, ackNo])+'\n'

        f = open('Sender_log.txt', 'a')
        f.write(log)
        f.close()
        pass
    # given a byte string as data
    # split the data into chunks as a list according to MSS
    def generate_chunk_list(self):
        data = self.data
        mss = self.mss
        mws = self.mws
        seqNo = self.seqNo
        # length of data
        data_length = len(data)

        # number of chunks that will be generated
        chunk_number = mws//mss
        # chunk list after split
        chunk_list = []
        
        # pack chunk_number of data
        # let current byte being packing be curr_pos
        curr_pos = seqNo-1
        for _ in range(chunk_number):
            # if no more data left, stop packing
            if curr_pos >= data_length:
                break
            # current package size is the minimum of max segment size and data left
            curr_pack_size = min(mss, data_length-curr_pos)
            # pack the packet and append to chunk_list
            chunk_list.append(data[curr_pos:curr_pos+curr_pack_size].encode())
            curr_pos += curr_pack_size

        # return the packets list, and the number of bytes in this list
        return chunk_list, curr_pos

    def establish_connection(self, s, ack):
        addr = self.dest_ip
        port = self.dest_port
        mss = self.mss
        write_log = self.write_log

        # create the SYN packet
        # assume the SYN packet has 1 bit random data
        packet = PacketEncoder(seqNo=self.seqNo, ptype='S', data=b'', mss=mss, ackNo=ack).encode_packet()

        # send the SYN packet and print the snd message
        # assume send to server's 0 seqNo
        s.sendto(packet, (addr, port))
        # write to log
        write_log('snd', 'S', self.seqNo, 0, ack)
        # receive the ack, SA
        res = s.recv(mss)
        # decode the package and print the recv message
        res = PacketDecoder(res).get_packet()
        # ack to receiver, which is the seqNo received from the receiver
        ack = res['seqNo']
        # SYN-ACK does not contains data, it takes 1 seqNo space
        self.seqNo = res['ackNo']
        # received packet type
        ptype = res['ptype']
        # print out the receive SA message
        # print to log
        write_log('recv', ptype, ack, 0, self.seqNo)
        # seqNo become the ackNo received from server

        # SYN-ACK does not contain any data, however it takes 1 seqNo, so ack need to be added by 1
        ack += 1

        # encode and send an ACK, assume server receive this and connection establish
        # assume this ACK contains no data, and ack number will be ack of received SA's seqNo
        packet = PacketEncoder(seqNo=self.seqNo, ptype='A', data=b'', mss=mss, ackNo=ack).encode_packet()
        s.sendto(packet, (addr, port))
        # write to log
        write_log('snd', 'A', self.seqNo, 0, ack)
        return ack

    def terminate_connection(self, s, ack):
        addr = self.dest_ip
        port = self.dest_port
        mss = self.mss
        write_log = self.write_log
        # encode and send FIN packet, assume FIN packet has no data
        packet = PacketEncoder(seqNo=self.seqNo, ptype='F').encode_packet()
        s.sendto(packet, (addr, port))
        # write to log
        write_log('snd', 'F', self.seqNo, 0, ack)

        # waiting for FIN-ACK
        while True:
            res = s.recv(mss)
            res = PacketDecoder(res).get_packet()
            # sequence number will be ack received from server
            self.seqNo = res['ackNo']
            # ack number will be sequence number received from server, plus the FA data length, which assumed to be 0
            ack = res['seqNo']
            # pack type can be read from received message
            ptype = res['ptype']
            if ptype == 'FA':
                # write to log
                write_log('recv', ptype, ack, 0, self.seqNo)
                break

        ack += 1

        packet = PacketEncoder(seqNo=self.seqNo, ptype='A').encode_packet()
        s.sendto(packet, (addr, port))
        # write to log
        write_log('snd', 'A', self.seqNo, 0, ack)
        s.close()

    # make statistic records
    def make_statistc(self):
        data = self.data
        self.data_amount = len(data)
        self.seg_num = math.ceil(len(data)/self.mss)
        pass
    
    # slide window
    def slide_window(self, s, ack):
        pl = self.pl
        write_log = self.write_log
        addr = self.dest_ip
        port = self.dest_port

        # if everything is sent, simply return without sending
        if self.last_send >= len(self.data):
            return self.last_send

        chunks, ws = self.generate_chunk_list()
        # index of the chunk to send after slide the window
        chunk_idx = (self.last_send - self.seqNo) // self.mss

        curr_seqNo = self.last_send
        for idx in range(chunk_idx, len(chunks)):
            chunk = chunks[idx]
            # generate packet, with packet type 'D'
            ptype = 'D'
            packet = PacketEncoder(seqNo=curr_seqNo, ptype=ptype, data=chunk, ackNo=ack).encode_packet()
            # simulate packet loss
            self.total_seg_num += 1
            if not pl.drop():
                # if not dropped, send data
                s.sendto(packet, (addr, port))

                write_log('snd', 'D', curr_seqNo, len(chunk), ack)
            else:
                write_log('drop', 'D', curr_seqNo, len(chunk), ack)
                self.drop_num += 1
            curr_seqNo += len(chunk)
        self.last_send = curr_seqNo
        return self.last_send
    # send data
    def send(self):
        overall_start = datetime.utcnow()
        # get address, port, data chunks, mss and mws ready
        mss = self.mss
        mws = self.mws
        timeout = self.timeout
        total_size = len(self.data)
        write_log = self.write_log

        # make some statics records
        self.make_statistc()

        # intialize a ack number, which is the ack received from server
        ack = 0
        # initialize a socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        ack = self.establish_connection(s, ack)
        # while not received the last byte
        while self.seqNo < total_size:
            # slide_window is called everytime a new ack is received
            ws = self.slide_window(s, ack)

            # number of repeated ack, for fast trasimission
            repeated_ack = 0

            # set timer for the sender to receive ack
            start_time = datetime.utcnow()
            s.settimeout(timeout)

            # while not time out
            while True:
                # if current time >= start time + timeout time
                if datetime.utcnow() >= start_time + timedelta(seconds=timeout):
                    # if timeout, restart timer and resend data, so break out from this loop
                    s.settimeout(0)
                    self.last_send = self.seqNo
                    break
                try:
                    # try to receive a result
                    res = s.recv(mss)

                    # unpack the result
                    res = PacketDecoder(res).get_packet()
                    # write to log
                    write_log('recv', res['ptype'], ack, 0, res['ackNo'])
                    # seqNo from server is the ackNo that sender will be send in next packet
                    ackNo = res['seqNo']
                    # ackNo from server is the data seqNo that server received from sender
                    seqNo = res['ackNo']

                    # repeated ack is received
                    if seqNo == self.seqNo:
                        repeated_ack += 1
                        self.dup_ack_num += 1
                        # if received 3 repeated ack, retransmit
                        if repeated_ack > 3:
                            self.last_send = self.seqNo
                            break
                    # previous ack is received
                    elif seqNo < self.seqNo:
                        self.dup_ack_num += 1
                        continue
                    # seqNo < ack < seqNo + mws, update self.seqNo and repeated_ack, 
                    # but do not stop timer and listen for futher ack
                    else:
                        # update the seqNo for sender
                        self.seqNo = seqNo
                        # update ackNo
                        ack = ackNo
                        '''
                        # if all the bytes that just sent are received, stop timer and send next group of chunks
                        if seqNo-1 == ws:
                        '''
                        # instead all the bytes that just sent are received, 
                        # when an valid ack is recevied, stop the timer and slide the window to send next chunk or group of chunks
                        break
                except socket.timeout as e:
                    # if timeout, restart timer and resend data, so break out from this loop
                    self.last_send = self.seqNo
                    break

        # close connection
        self.terminate_connection(s, ack)
        total_transmission_time = datetime.utcnow() - overall_start
        self.total_time = total_transmission_time

        f = open("Sender_log.txt", "a")
        f.write('\n')
        f.write("Amount of (original) Data Transferred (in bytes): %d\n" % self.data_amount)
        f.write("Number of Data Segments Sent (excluding retransmissions): %d\n" % self.seg_num)
        f.write("Number of (all) Packets Dropped (by the PL module): %d\n" % self.drop_num)
        f.write("Number of Retransmitted Segments: %d\n" % (self.total_seg_num - self.seg_num))
        f.write("Number of Duplicate Acknowledgements received: %d\n" % self.dup_ack_num)
        f.write(f"Total transmission time {total_transmission_time}")
        f.close()

    def get_total_time(self):
        return self.total_time.microseconds

    # show sender info
    def __repr__(self):
        return str([self.dest_ip, self.dest_port, self.mss, self.mws, self.data, self.timeout])

class PacketLoss:
    def __init__(self, pdrop, seed):
        self.pdrop = pdrop
        random.seed(seed)
    
    def drop(self):
        curr = random.random()
        return True if curr < self.pdrop else False
        
if __name__ == '__main__':
    # initialize(dest_ip, dest_port, mss, mws, file, timeout)
    args = sys.argv
    arg_size = len(args)
    receiver_host_ip = args[1] if arg_size > 1 else '127.0.0.1'
    receiver_port = int(args[2]) if arg_size > 2 else 8000
    file_name = args[3] if arg_size > 3 else '32KB.txt'
    mws = int(args[4]) if arg_size > 4 else 500
    mss = int(args[5]) if arg_size > 5 else 50
    timeout = float(args[6]) if arg_size > 6 else 5   # the timeout arg is in ms, so convert this to ms
    timeout /= 1000
    pdrop = float(args[7]) if arg_size > 7 else 0.1
    seed = int(args[8]) if arg_size > 8 else 300

    sender = Sender(receiver_host_ip, receiver_port, file_name, mws, mss, timeout, pdrop, seed)
    sender.send()