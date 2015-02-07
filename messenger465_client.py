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
    def __init__(self, host, port):
        '''
        Constructor.  You should create a new socket
        here and do any other initialization.
        '''
        self.host = host
        self.port = port
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        except Exception as e:
            print("Got exception type: ", type(e))
            print(str(e))

    def getMessages(self):
        '''
        You should make calls to get messages from the message
        board server here.
        '''
        get_request = "AGET"
        get_request = get_request.encode()
        msg_list = []

        try:
            self.sock.sendto(get_request, (self.host, self.port))

            rv = select([self.sock], [], [], 0.1)
            if len(rv[0]) == 0:
                raise OSError("No messages available!")

            (msg_data, server_address) = self.sock.recvfrom(1400)

            msg_data = msg_data.decode()

            if msg_data.startswith("AOK"):
                msg_list = msg_data[4:].split("::")
            elif msg_data.startswith("AERROR"):
                raise IOError(msg_data)

            message_strings = []
            for i in range(0, len(msg_list)-2, 3):
                message_strings.append(" ".join(msg_list[i:i+3]))

            return message_strings

        except Exception as e:
            print("Got exception type: ", type(e))
            print(str(e))

    def postMessage(self, user, message):
        '''
        You should make calls to post messages to the message
        board server here.
        '''

        if len(message) > 60:
            return "Message too long! (Max length 60 characters)"
        elif "::" in message:
            return "Message invalid! Contains '::'"

        post_request = "APOST " + user + "::" + message
        post_request = post_request.encode()

        status_string = ""

        try:
            self.sock.sendto(post_request, (self.host, self.port))
            select([self.sock], [], [], 0.1)
            status_string = "Sent!"
        except Exception as e:
            print("Got exception type: ", type(e))
            print(str(e))
            status_string = "Error!"

        return status_string


class MessageBoardController(object):
    '''
    Controller class in MVC pattern that coordinates
    actions in the GUI with sending/retrieving information
    to/from the server via the MessageBoardNetwork class.
    '''

    def __init__(self, myname, host, port):
        self.name = myname
        self.view = MessageBoardView(myname)
        self.view.setMessageCallback(self.post_message_callback)
        self.net = MessageBoardNetwork(host, port)

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
        self.view.setStatus(self.net.postMessage(self.name, m))

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

                #if len(display_strings) != 0:
                    #self.view.setStatus("Retrieved {} messages".format(len(display_strings)))
                #else:
                    #self.view.setStatus("")
        except OSError as e:
            self.view.setStatus("Error!")
            print(type(e), str(e))

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
    args = parser.parse_args()

    user_name_invalid  = True
    while user_name_invalid:
        myname = input("What is your user name (max 8 characters)? ")
        if "::" in myname:
            print("Username invalid, contains '::'")
        elif len(myname) > 8:
            print("Username too long!")
        else:
            user_name_invalid = False

    app = MessageBoardController(myname, args.host, args.port)
    app.run()

