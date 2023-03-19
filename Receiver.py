import socket
import my_protocol as prt
from tkinter import *
import time
from pathlib import Path

MAX_SEQ_NUM = int.from_bytes(b'\xff\xff\xff\xff', byteorder='big')


class Receiver:
    def __init__(self, ip_addr, port, output, dir):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.bind((ip_addr, int(port)))
        self.frag_length = 0
        self.output = output
        self.status = 1  # 1-receiving, 2-receiving message, 3-receiving file name, 4-receiving file, 5-keeping alive
        self.seq_num = 0
        self.file_name = ''
        self.received_data = bytes()
        self.frag_num = 0
        self.sender_addr = None
        self.dir = dir+'/'


    def display_log(self, log):
        self.output.insert(END, log + '\n')

    # Resend ACK for the last fragment
    def resend_ack(self):
        if self.status == 3:
            self.sock.sendto(prt.create_header('a', self.seq_num, None), self.sender_addr)
        else:
            self.sock.sendto(prt.create_header('A', self.seq_num, None), self.sender_addr)

    # Handle received corrupted fragment
    def send_nack(self, data, addr):
        if 2 <= self.status <= 4:  # Expected packet was corrupted
            self.display_log(f'{self.frag_num + 1}. Received data fragment ({len(data) - 7} bytes) - NOT OK')
        if self.status == 5:  # Corrupted keepalive
            self.sock.sendto(prt.create_header('N', MAX_SEQ_NUM, None), addr)
        else:
            self.sock.sendto(prt.create_header('N', self.seq_num, None), addr)

    # Long function that sends responses according to flag and status and calls handler functions
    # Covers every possibility explicitly
    def respond(self, data, addr):
        if prt.check_crc(data):
            flag = data[0:1].decode('utf-8')
            seq_num = int.from_bytes(data[1:5], byteorder="big")
            data = data[7:]
            if flag == 'M' or flag == 'L':
                self.sender_addr = addr
                self.frag_length = seq_num
                self.seq_num = 0
                self.handle_connect(flag)
                self.sock.sendto(prt.create_header('A', self.seq_num, None), addr)
            elif (self.status != 3 or flag == 'I') and seq_num == self.seq_num - self.frag_length:  # Old fragment
                self.resend_ack()
            elif (self.status == 2 or self.status == 4) and (flag == 'P' or flag == 'F') and self.seq_num == seq_num:
                self.seq_num += self.frag_length
                self.handle_data(flag, data)
                self.sock.sendto(prt.create_header('A', self.seq_num, None), addr)
            elif self.status == 3:
                if flag == 'I' and self.seq_num == seq_num:
                    self.seq_num += self.frag_length
                    self.handle_filename(data)
                    self.sock.sendto(prt.create_header('a', self.seq_num, None), addr)
                if flag == 'P' or flag == 'F':
                    self.seq_num = self.frag_length
                    self.handle_data(flag, data)
                    self.sock.sendto(prt.create_header('A', self.seq_num, None), addr)
            elif self.status == 5:
                if flag == 'K' and seq_num == MAX_SEQ_NUM:
                    self.display_log('Keepalive :' + str(time.strftime('%H:%M:%S')))
                    self.sock.sendto(prt.create_header('A', MAX_SEQ_NUM, None), addr)
                if flag == 'B':
                    self.display_log('Transmission ended (by other side)')
                    self.status = 1
        else: self.send_nack(data, addr)

    # Establish connection with sender node
    def handle_connect(self, flag):
        if flag == 'M':
            self.status = 2
            self.display_log('Establishing connection to receive a message')
        elif flag == 'L':
            self.status = 3
            self.display_log('Establishing connection to receive a file')
        self.sock.setblocking(True)
        self.sock.settimeout(1)

    # Append received data, if its the last fragment save it or print it to output
    def handle_data(self, flag, data):
        if self.status == 3:
            self.status = 4
        if flag == 'P':
            if self.status == 2 or self.status == 4:
                self.frag_num += 1
                self.received_data += data
                self.display_log(f'{self.frag_num}. Received data fragment ({len(data)} bytes) - OK')
        elif flag == 'F':
            self.frag_num += 1
            self.sock.setblocking(False)
            self.received_data += data
            self.display_log(f'{self.frag_num}. Received data fragment ({len(data)} bytes) - OK')
            self.frag_num = 0
            if self.status == 2:
                self.display_log('Complete message: ' + str(self.received_data.decode('utf-8')))
            elif self.status == 4:
                with open(self.dir + self.file_name, 'wb') as file:
                    file.write(self.received_data)
                    file_path = Path(self.dir + self.file_name).resolve()
                    self.display_log('Successfully downloaded file to: ' + str(file_path))
            self.received_data = bytes()
            self.file_name = ''
            self.status = 5

    # Append data to filename
    def handle_filename(self, data):
        self.file_name += data.decode('utf-8')
        self.display_log(f'Received file name fragment ({len(data)} bytes)')

    # Receive data and send it to self.respond() for handling
    def receive(self):
        while self.status > 0:
            try:
                data, addr = self.sock.recvfrom(4096)
                self.respond(data, addr)
                if self.status == 5:
                    self.keepalive_phase()
            except socket.error:
                if 2 <= self.status <= 4:   # Resend ACK if timeout
                    self.resend_ack()
                continue

    # Await keepalives from sender, if 3 timers expire then close the connection
    def keepalive_phase(self):
        ka_limit = 10
        self.sock.setblocking(False)
        waiting = True
        elapsed_timers = 0
        start = time.time()
        while self.status == 5 and elapsed_timers < 3:
            try:
                if waiting:
                    if time.time() - start > ka_limit:
                        elapsed_timers += 1
                        start = time.time()
                data, addr = self.sock.recvfrom(4096)
                self.respond(data, addr)
                elapsed_timers = 0
                start = time.time()
            except socket.error:
                continue
        if self.status == 5:
            self.display_log("Connection ended: no keepalive")
            self.status = 1
        elif self.status == 0:
            self.sock.sendto(prt.create_header('B', MAX_SEQ_NUM, None), self.sender_addr)
