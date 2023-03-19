from tkinter import *
from tkinter.filedialog import askopenfilename
from tkinter.filedialog import askdirectory
from tkinter import messagebox
import tkinter.scrolledtext as st
import threading
from Sender import Sender
from Receiver import Receiver

MAX_FRAG_SIZE = 1465


class CommNode:
    def __init__(self, master):
        self.master = master
        self.sender = None
        self.receiver = None
        self.ip_addr = StringVar(master, value="127.0.0.1")
        self.port = StringVar(master, value="12345")
        self.master.title("Communication Node")
        self.filename = StringVar(master, value="No file chosen")
        self.dirname = StringVar(master, value="my_downloads")
        self.is_bad_frag = IntVar()
        self.send_msg_thread = None
        self.send_file_thread = None
        self.rec_thread = None
        self.stop_trans_button = None
        self.create_frames()
        self.make_top()
        self.make_ctrl_panel()
        self.make_output()
        self.master.mainloop()

    def create_frames(self):
        self.frame0 = Frame(self.master)
        self.frame1 = Frame(self.master)
        self.frame2 = Frame(self.master)
        self.frame3 = Frame(self.master)
        self.frame4 = Frame(self.master)
        self.frame5 = Frame(self.master)
        self.frame6 = Frame(self.master)
        self.frame7 = Frame(self.master)

    # Create the unchanging top part of the GUI
    def make_top(self):
        self.ip_lbl = Label(self.frame0, text="IP address: ")
        self.ip_entry = Entry(self.frame0, textvariable=self.ip_addr)
        self.port_lbl = Label(self.frame0, text="Port: ")
        self.port_entry = Entry(self.frame0, textvariable=self.port)
        self.file_lbl = Label(self.frame1, textvariable=self.filename)
        self.choose_file_button = Button(self.frame1, text="Choose file", command=self.choose_file)
        self.dir_lbl = Label(self.frame2, textvariable=self.dirname)
        self.choose_dir_button = Button(self.frame2, text="Choose directory for downloads", command=self.choose_dir)
        self.message_lbl = Label(self.frame3, text="Message:")
        self.message_entry = Entry(self.frame3, width=80)
        self.frag_size_lbl = Label(self.frame4, text=f'Fragment size(MAX = {MAX_FRAG_SIZE}):')
        self.frag_size_entry = Entry(self.frame4)
        self.frame0.pack()
        self.ip_lbl.pack(side=LEFT)
        self.ip_entry.pack(side=LEFT)
        self.port_lbl.pack(side=LEFT)
        self.port_entry.pack(side=LEFT)
        self.frame1.pack()
        self.file_lbl.pack(side=LEFT)
        self.choose_file_button.pack(side=LEFT)
        self.frame2.pack()
        self.dir_lbl.pack(side=LEFT)
        self.choose_dir_button.pack(side=LEFT)
        self.frame3.pack()
        self.message_lbl.pack(side=LEFT)
        self.message_entry.pack(side=LEFT)
        self.frame4.pack(side=TOP)
        self.frag_size_lbl.pack(side=LEFT)
        self.frag_size_entry.pack(side=LEFT)

    # Create the dynamic control panel
    def make_ctrl_panel(self):
        self.receive_button = Button(self.frame5, text="RECEIVE", command=self.start_receive)
        self.send_message_button = Button(self.frame5, text="SEND MESSAGE", command=self.start_send_msg)
        self.send_file_button = Button(self.frame5, text="SEND FILE", command=self.start_send_file)
        self.stop_trans_button = Button(self.frame5, text="Stop transmission", command=self.stop_transmission)
        self.bad_frag_lbl = Label(self.frame6, text='Bad fragment: ')
        self.bad_frag_entry = Entry(self.frame6)
        self.bad_frag_check = Checkbutton(self.frame6, text='Include bad fragment', variable=self.is_bad_frag,
                                          onvalue=1, offvalue=0)
        self.frame5.pack()
        self.receive_button.pack(side=LEFT)
        self.send_message_button.pack(side=LEFT)
        self.send_file_button.pack(side=LEFT)
        self.stop_trans_button.pack(side=LEFT)
        self.frame6.pack()
        self.bad_frag_lbl.pack(side=LEFT)
        self.bad_frag_entry.pack(side=LEFT)
        self.bad_frag_check.pack(side=LEFT)

    def destroy_ctrl_panel(self):
        self.receive_button.destroy()
        self.send_message_button.destroy()
        self.send_file_button.destroy()
        self.stop_trans_button.destroy()
        self.bad_frag_lbl.destroy()
        self.bad_frag_entry.destroy()
        self.bad_frag_check.destroy()

    def make_output(self):
        self.output = st.ScrolledText(self.frame7)
        self.clear_button = Button(self.frame7, text='Clear', command=lambda: self.output.delete('1.0', END))
        self.frame7.pack()
        self.output.pack()
        self.clear_button.pack(side=BOTTOM)

    # Create a receiver object and start its receive thread
    def start_receive(self):
        try:
            self.receiver = Receiver(self.ip_addr.get(), self.port.get(), self.output,  self.dirname.get())
            self.show_receiving()
            self.rec_thread = threading.Thread(target=self.receiver.receive, daemon=True)
            self.rec_thread.start()
        except OSError or ValueError:
            messagebox.showerror("Error: Invalid socket", "Socket is already used or invalid")

    def start_send_msg(self):
        message = self.message_entry.get()
        try:
            frag_size = int(self.frag_size_entry.get())
        except ValueError:
            messagebox.showerror("Error: No fragment size", "Please input a fragment size")
            return
        if message and frag_size:
            if frag_size > MAX_FRAG_SIZE:
                messagebox.showerror("Error: Exceeded max fragment size", "max fragment size is " + str(MAX_FRAG_SIZE))
                return
            self.stop_keepalive()
            try:
                if self.is_bad_frag.get() and self.bad_frag_entry.get():
                    self.sender = Sender(self.ip_addr.get(), self.port.get(), self.output, message,
                                         frag_size, int(self.bad_frag_entry.get()))
                else: self.sender = Sender(self.ip_addr.get(), self.port.get(), self.output, message, frag_size, 0)
                self.send_msg_thread = threading.Thread(target=self.sender.send_message, daemon=True)
                self.send_msg_thread.start()
            except ValueError:
                messagebox.showerror("Error: Value Error", 'Invalid input')

    def start_send_file(self):
        file = self.filename.get()
        try:
            frag_size = int(self.frag_size_entry.get())
        except ValueError:
            messagebox.showerror("Error: No fragment size", "Please input a fragment size")
            return
        if file != "No file chosen" and frag_size:
            if frag_size > MAX_FRAG_SIZE:
                messagebox.showerror("Error: Exceeded max fragment size", "max fragment size is " + str(MAX_FRAG_SIZE))
                return
            self.stop_keepalive()
            try:
                if self.is_bad_frag.get() and self.bad_frag_entry.get():
                    self.sender = Sender(self.ip_addr.get(), self.port.get(), self.output,  file,
                                         frag_size, int(self.bad_frag_entry.get()))
                else: self.sender = Sender(self.ip_addr.get(), self.port.get(), self.output, file, frag_size, 0)
                self.send_file_thread = threading.Thread(target=self.sender.send_file, daemon=True)
                self.send_file_thread.start()
            except ValueError:
                messagebox.showerror("Error: Value Error", 'Invalid input')

    # Stops sender from sending (only usable during keepalive phase)
    def stop_transmission(self):
        if self.sender and self.sender.status == 5:
            self.stop_keepalive()
            self.output.insert(END, 'Transmission ended (by this side)\n')

    # Stop the sender from sending keepalives
    def stop_keepalive(self):
        if self.send_msg_thread and self.send_msg_thread.is_alive():
            self.sender.status = 0
            self.send_msg_thread.join()
        elif self.send_file_thread and self.send_file_thread.is_alive():
            self.sender.status = 0
            self.send_file_thread.join()

    def stop_receive(self):
        if self.receiver.status == 5:
            self.output.insert(END, 'Transmission ended (by this side)\n')
        self.receiver.status = 0
        self.rec_thread.join()
        self.receiver.sock.close()

    # Destroy widgets showing the receiving process
    def stop_rec_process(self):
        if self.rec_thread.is_alive():
            self.stop_receive()
        self.process_lbl.destroy()
        self.stop_button.destroy()
        self.choose_dir_button["state"] = NORMAL
        self.choose_file_button["state"] = NORMAL
        self.make_ctrl_panel()

    # Destroy unnecessary widgets and show that the node is ready to receive data
    def show_receiving(self):
        self.choose_dir_button["state"] = DISABLED
        self.choose_file_button["state"] = DISABLED
        self.destroy_ctrl_panel()
        self.process_lbl = Label(self.frame5, text='Receiving...')
        self.stop_button = Button(self.frame5, text="STOP", command=self.stop_rec_process)
        self.frame5.pack()
        self.process_lbl.pack(side=LEFT)
        self.stop_button.pack(side=LEFT)

    # User selects any file
    def choose_file(self):
        file = askopenfilename(title="Select a file")
        if file:
            self.filename.set(file)

    # User selects any directory
    def choose_dir(self):
        dir = askdirectory(title="Select a directory")
        if dir:
            self.dirname.set(dir)

root = Tk()
app = CommNode(root)
