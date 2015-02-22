#!/usr/bin/env python3

__author__ = "jsommers@colgate.edu"
__doc__ = '''
A simple model-view controller-based message board/chat client application.
'''
import sys
if sys.version_info[0] != 3:
    print ("This code must be run with a python3 interpreter!")
    sys.exit()

import tkinter
import socket
from select import select
import argparse

status_timeout = 0

class AppError(Exception):
    ''''Base exception class for errors in the client application'''
    pass

class DataError(AppError):
    '''class for data corruption errors (checksum)'''
    pass

class ServerError(AppError):
    '''class for server reponse errors'''
    pass

class RequestError(AppError):
    '''class for request errors'''
    pass

class PostError(RequestError):
    ''''class for post errors'''
    pass

class GetError(RequestError):
    ''''class for post errors'''
    pass

class MessageBoardNetwork(object):
    '''
    Model class in the MVC pattern.  This class handles
    the low-level network interactions with the server.
    It should make GET requests and POST requests (via the
    respective methods, below) and return the message or
    response data back to the MessageBoardController class.

    host --> ip address of messageboard server
    port --> UDP port that server is listening to
    '''
    def __init__(self, host, port, retries, timeout):
        '''
        Constructor.  You should create a new socket
        here and do any other initialization.
        '''
        self.host = host
        self.port = port
        self.sequence_char = '0'
        self.retries = retries
        self.timeout = timeout
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        except socket.error as e:
            print("Got exception type: ", type(e))
            print(str(e))

    @staticmethod
    def lrc(data_string):
        '''
        takes a string a returns a XOR checksum in integer form
        '''
        message_in_bytes = bytearray(data_string, 'ascii')
        checksum = 0
        for b in message_in_bytes:
            checksum ^= b
        return checksum

    def getMessages(self):
        '''
        You should make calls to get messages from the message
        board server here.
        '''
        message_strings = []
        msg_list = []
        ack = self.makeRequest(0, "", "")
        if ack == "FAIL":
            raise GetError("Server Never responded!")
        elif "OK" in ack:
            msg_list = ack[6:].split("::")
        elif "ERROR" in ack:
            raise GetError(ack)
        else:
            raise GetError("invalid response received from server!")

        for i in range(0, len(msg_list)-2, 3):
             message_strings.append(" ".join(msg_list[i:i+3]))

        return message_strings

    def postMessage(self, user, message):
        '''
        You should make calls to post messages to the message
        board server here.
        '''
        ack = self.makeRequest(1, user, message)
        if ack == "FAIL":
            raise PostError("Server never responded!")
        elif "OK" in ack:
            status_string = "Message Sent!"
        elif "ERROR" in ack:
            if len(message) > 60:
                status_string = "Message too long! (Max length 60 characters)"
            elif "::" in message:
                status_string = "Message invalid! Contains '::'"
            elif "::" in user:
                status_string = "Username invalid! Contains '::'"
        else:
            raise PostError("Invalid response received from server!")

        return status_string

    def makeRequest(self, request_type, user, message):
        '''
        Used to make GET and POST actions.
        Returns the server's reponse string.
        For GET actions, request_type is 0;
        user and message are passed as empty strings.
        For POST actions, request_type is 1;
        username and message are provided as args.
        '''

        if request_type == 0:
            data = "GET"
        elif request_type == 1:
            data = "POST " + user + "::" + message
        else:
            raise AppError("unsupported request type")

        checksum = self.lrc(data)
        header = 'C' + self.sequence_char + chr(checksum)
        message = header + data
        request = message.encode()

        attempts = 0
        while attempts < self.retries:
            self.sock.sendto(request, (self.host, self.port))
            read_list = select([self.sock], [], [], self.timeout)
            if len(read_list[0]) != 0:
                (ack, server_address) = self.sock.recvfrom(1400)
                ack = ack.decode()
                received_seq = ack[1]
                if received_seq == self.sequence_char:
                    received_checksum = ack[2]
                    message = ack[3:]
                    my_checksum = self.lrc(ack[3:])
                    if chr(my_checksum) == received_checksum:
                        if self.sequence_char == '0':
                            self.sequence_char = '1'
                        else:
                            self.sequence_char = '0'
                        return ack
                    else:
                        attempts += 1
                else:
                    attempts += 1
            else:
                attempts += 1

        return "FAIL"


class MessageBoardController(object):
    '''
    Controller class in MVC pattern that coordinates
    actions in the GUI with sending/retrieving information
    to/from the server via the MessageBoardNetwork class.
    '''

    def __init__(self, myname, host, port, retries, timeout):
        self.name = myname
        self.view = MessageBoardView(myname)
        self.view.setMessageCallback(self.post_message_callback)
        self.net = MessageBoardNetwork(host, port, retries, timeout)

    def run(self):
        self.view.after(1000, self.retrieve_messages)
        self.view.mainloop()

    def post_message_callback(self, m):
        '''
        This method gets called in response to a user typing in
        a message to send from the GUI.  It should dispatch
        the message to the MessageBoardNetwork class via the
        postMessage method.
        '''
        global status_timeout
        status_timeout = 0
        try:
            self.view.setStatus(self.net.postMessage(self.name, m))
        except socket.error as e:
            self.view.setStatus("Socket Error! "+ str(e))
        except PostError as e:
            self.view.setStatus("POST Error! " + str(e))
        except ServerError as e:
            self.view.setStatus("Server Error!" + str(e))
        except UnicodeError as e:
            self.view.setStatus("Error! Data corrupted!")
        except Exception as e:
            error_msg = "Error! {} {}".format(type(e), str(e))
            print(error_msg)
            self.view.setStatus(error_msg)

    def retrieve_messages(self):
        '''
        This method gets called every second for retrieving
        messages from the server.  It calls the MessageBoardNetwork
        method getMessages() to do the "hard" work of retrieving
        the messages from the server, then it should call
        methods in MessageBoardView to display them in the GUI.

        You'll need to parse the response data from the server
        and figure out what should be displayed.

        Two relevant methods are (1) self.view.setListItems, which
        takes a list of strings as input, and displays that
        list of strings in the GUI, and (2) self.view.setStatus,
        which can be used to display any useful status information
        at the bottom of the GUI.
        '''
        global status_timeout
        status_timeout = (status_timeout + 1) % 5

        if status_timeout % 5 == 0:
            self.view.setStatus("")

        self.view.after(1000, self.retrieve_messages)
        try:
            display_strings = self.net.getMessages()
            if len(display_strings) > 0:
                self.view.setListItems(display_strings)
        except socket.error as e:
            self.view.setStatus("Socket Error! "+ str(e))
        except GetError as e:
            self.view.setStatus("GET Error! " + str(e))
        except UnicodeError as e:
            self.view.setStatus("Error! Data corrupted!")
        except Exception as e:
            error_msg = "Error! {} {}".format(type(e), str(e))
            print(error_msg)
            self.view.setStatus(error_msg)

class MessageBoardView(tkinter.Frame):
    '''
    The main graphical frame that wraps up the chat app view.
    This class is completely written for you --- you do not
    need to modify the below code.
    '''
    def __init__(self, name):
        self.root = tkinter.Tk()
        tkinter.Frame.__init__(self, self.root)
        self.root.title('{} @ messenger465'.format(name))
        self.width = 80
        self.max_messages = 20
        self._createWidgets()
        self.pack()

    def _createWidgets(self):
        self.message_list = tkinter.Listbox(self, width=self.width, height=self.max_messages)
        self.message_list.pack(anchor="n")

        self.entrystatus = tkinter.Frame(self, width=self.width, height=2)
        self.entrystatus.pack(anchor="s")

        self.entry = tkinter.Entry(self.entrystatus, width=self.width)
        self.entry.grid(row=0, column=1)
        self.entry.bind('<KeyPress-Return>', self.newMessage)

        self.status = tkinter.Label(self.entrystatus, width=self.width, text="starting up")
        self.status.grid(row=1, column=1)

        self.quit = tkinter.Button(self.entrystatus, text="Quit", command=self.quit)
        self.quit.grid(row=1, column=0)


    def setMessageCallback(self, messagefn):
        '''
        Set up the callback function when a message is generated
        from the GUI.
        '''
        self.message_callback = messagefn

    def setListItems(self, mlist):
        '''
        mlist is a list of messages (strings) to display in the
        window.  This method simply replaces the list currently
        drawn, with the given list.
        '''
        self.message_list.delete(0, self.message_list.size())
        self.message_list.insert(0, *mlist)

    def newMessage(self, evt):
        '''Called when user hits entry in message window.  Send message
        to controller, and clear out the entry'''
        message = self.entry.get()
        if len(message):
            self.message_callback(message)
        self.entry.delete(0, len(self.entry.get()))

    def setStatus(self, message):
        '''Set the status message in the window'''
        self.status['text'] = message

    def end(self):
        '''Callback when window is being destroyed'''
        self.root.mainloop()
        try:
            self.root.destroy()
        except:
            pass

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='COSC465 Message Board Client')
    parser.add_argument('--host', dest='host', type=str, default='localhost',
                        help='Set the host name for server to send requests to (default: localhost)')
    parser.add_argument('--port', dest='port', type=int, default=1111,
                        help='Set the port number for the server (default: 1111)')
    parser.add_argument("--retries", dest='retries', type=int, default=3,
                        help='Set the number of retransmissions in case of a timeout')
    parser.add_argument("--timeout", dest='timeout', type=float, default=0.1,
                        help='Set the RTO value')
    args = parser.parse_args()

    #user_name_invalid  = True
    #while user_name_invalid:
        #myname = input("What is your user name (max 8 characters)? ")
        #if "::" in myname:
            #print("Username invalid, contains '::'")
        #elif len(myname) > 8:
            #print("Username too long!")
        #else:
            #user_name_invalid = False

    myname = input("What is your user name (max 8 characters)? ")
    app = MessageBoardController(myname, args.host, args.port,
                                 args.retries, args.timeout)
    print("args.host: " + str(args.host) + " | args.port: " + str(args.port))
    app.run()

