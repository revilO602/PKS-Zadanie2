import socket
import my_protocol as prt
from tkinter import *
from pathlib import Path
import time

MAX_SEQ_NUM = int.from_bytes(b'\xff\xff\xff\xff', byteorder='big')


class Sender:
    def __init__(self, ip_addr, port, output, data, frag_size, bad_frag):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1)
        self.receiver = (ip_addr, int(port))
        self.output = output
        self.data = data
        self.frag_size = frag_size
        self.seq_num = 0
        self.status = 1  # 1-sending, 2-sending message, 3-sending file name, 4-sending file, 5-keeping alive
        self.bad_frag = bad_frag  # Index of bad fragment, 0 if no bad fragment
        self.rezia = 0

    def display_log(self, log):
        self.output.insert(END, log + '\n')

    # Check if receivers response is what was expected (explicitly check if its appropriate for sender status)
    def check_response(self, response):
        flag = response[0:1].decode('utf-8')
        if prt.check_crc(response) and flag != 'N':
            seq_num = int.from_bytes(response[1:5], byteorder="big")
            if self.status == 1 and seq_num == 0 and flag == 'A':
                return True
            if self.status == 2 and seq_num == self.seq_num + self.frag_size and flag == 'A':
                return True
            if self.status == 3 and seq_num == self.seq_num + self.frag_size and flag == 'a':
                return True
            if self.status == 4 and seq_num == self.seq_num + self.frag_size and flag == 'A':
                return True
            if self.status == 5 and seq_num == MAX_SEQ_NUM:
                if flag == 'A':
                    return True
                if flag == 'B':
                    self.status = 1
                    self.display_log('Transmission ended (by other side)')
            return False
        return False

    # Establish connection with server - inform server what type of data will be sent and wait for ACK
    def establish_connection(self, type):
        flag = type
        self.status = 1
        while True:
            try:
                self.sock.sendto(prt.create_header(flag, self.frag_size, None), self.receiver)
                self.rezia += 7
                response = self.sock.recvfrom(4096)[0]
                if self.check_response(response):
                    self.display_log("Connection established")
                    return True
                else:
                    continue
            except socket.timeout:
                self.display_log("Retrying to establish connection... (timeout)")
                continue
            except ConnectionResetError:
                self.display_log('Receiver is offline!')
                self.status = 0
                return False

    # Divides data into fragments with header
    def fragmentify(self, data, is_filename=False):
        new_data = []
        if not is_filename:
            for i in range(0, len(data), self.frag_size):
                if i + self.frag_size >= len(data):  # Last fragment
                    new_data.append(prt.create_header('F', i, data[i: i + self.frag_size]))
                else:
                    new_data.append(prt.create_header('P', i, data[i: i + self.frag_size]))
        else:
            for i in range(0, len(data), self.frag_size):
                new_data.append(prt.create_header('I', i, data[i: i + self.frag_size]))
        return new_data

    # Send data fragments in order and wait for response (socket blocks)
    def send_data(self, data):
        fragment = next(data)
        frag_num = 1
        while True:
            try:
                self.seq_num = int.from_bytes(fragment[1:5], byteorder="big")
                if self.status != 3:
                    self.display_log(f'{frag_num}. Sending data fragment ({len(fragment) - 7} bytes)')
                if frag_num == self.bad_frag and (self.status == 2 or self.status == 4):    # Send corrupted fragment
                    self.sock.sendto(prt.make_mistake(fragment), self.receiver)
                    self.rezia += 7
                    self.bad_frag = 0
                else:
                    self.sock.sendto(fragment, self.receiver)
                    self.rezia += 7
                response, addr = self.sock.recvfrom(4096)
                if self.check_response(response):
                    fragment = next(data)
                    frag_num += 1
                else:
                    continue
            except StopIteration:
                break
            except socket.timeout:
                continue
            except ConnectionResetError:
                self.display_log('Receiver is offline!')
                self.status = 0
                break

    # Establish connection for message transfer -> send message as data
    def send_message(self):
        self.data = self.data.encode('utf-8')
        data = iter(self.fragmentify(self.data))
        if self.establish_connection('M'):
            self.status = 2
            self.send_data(data)
            self.display_log('Message successfully sent!')
            self.display_log(f'Celkova rezia: {self.rezia} bajtov')
            if self.status > 0:
                self.keepalive_phase()

    # Establish connection for file transfer -> send file name, then file data
    def send_file(self):
        file = open(self.data, 'rb')    # Path to file is data at the start
        file_name = Path(self.data).name.encode('utf-8')
        file_name = iter(self.fragmentify(file_name, True))
        data = file.read()
        data = iter(self.fragmentify(data))
        if self.establish_connection('L'):
            self.status = 3
            self.display_log('Sending file name...')
            self.send_data(file_name)
            self.status = 4
            self.send_data(data)
            self.display_log(f'File successfully sent from: {self.data}')
            self.display_log(f'Celkova rezia: {self.rezia} bajtov')
            if self.status > 0:
                self.keepalive_phase()

    # Start sending keepalives - if 3 in a row aren't acknowledged, than close the connection
    def keepalive_phase(self):
        ka_limit = 10
        self.sock.setblocking(False)
        self.status = 5
        waiting = False
        misses_amount = 0
        start = time.time() - ka_limit
        while self.status == 5 and misses_amount < 3:
            try:
                if not waiting and time.time() - start >= ka_limit:
                    self.sock.sendto(prt.create_header('K', MAX_SEQ_NUM, None), self.receiver)
                    self.display_log('Keepalive :' + str(time.strftime('%H:%M:%S')))
                    start = time.time()
                    waiting = True
                if waiting:
                    if time.time() - start > ka_limit:
                        misses_amount += 1
                        waiting = False
                response, addr = self.sock.recvfrom(4096)
                if self.check_response(response):
                    waiting = False
                    start = time.time()
                    misses_amount = 0
                elif self.status == 5:
                    self.sock.sendto(prt.create_header('K', MAX_SEQ_NUM, None), self.receiver)
            except socket.error:
                continue
            except ConnectionResetError:
                self.display_log('Receiver is offline!')
                self.status = 0
                return
        if self.status == 5:
            self.display_log("Connection ended: no response to keepalive")
            self.sock.close()
        elif self.status == 0:
            self.sock.sendto(prt.create_header('B', MAX_SEQ_NUM, None), self.receiver)
