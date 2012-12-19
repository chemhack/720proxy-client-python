import SocketServer
import getpass
import os
import socket
import string
import struct
import urllib
import json
import ConfigParser
import select

config = ConfigParser.RawConfigParser()

SETTING_PATH = os.path.expanduser("~/.720proxy_profile")
API_URL='http://720proxy.com/api/'

def initConfig():
    if config.has_section('720Proxy'):
        config.remove_section('720Proxy')
    config.add_section('720Proxy')
    config.set('720Proxy', 'socksPort', '2333')
    config.set('720Proxy', 'token', '')
    config.set('720Proxy', 'server_host', '')
    config.set('720Proxy', 'server_socks_port', '')

def saveConfig():
    config.write(open(SETTING_PATH, 'w+'))


def loadConfig():
    config.read(SETTING_PATH)
    if not config.has_section('720Proxy'):
        initConfig()
        saveConfig()


def login():
    print "Attempting login to 720 proxy...."
    email = raw_input("Email:")
    password = getpass.getpass("Password:")
    url = API_URL+'auth?email=' + urllib.quote(email) + '&password=' + urllib.quote(password)
    result = json.load(urllib.urlopen(url))
    if result['status'] == 'ok':
        token = result['token']
        config.set('720Proxy', 'token', token)
        print "Please select the server to use, "
        servers=result['servers']
        for i in range(len(servers)):
            print '%d - %s:%d' % (i,servers[i]['host'],servers[i]['socksPort'])
        seleceted = int(raw_input("Select a server[0-%d]:"%(len(servers)-1)))
        config.set('720Proxy', 'server_host', servers[seleceted]['host'])
        config.set('720Proxy', 'server_socks_port', servers[seleceted]['socksPort'])
        saveConfig()
        print "Logged in, credential saved in " + SETTING_PATH
    elif result['status'] == 'false_credential':
        print "Password or Email incorrect, retrying..."
        login()
    else:
        print "Unexpected error, " + result['status']


class ThreadingTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address=True
    pass


class ProxyTCPHandler(SocketServer.StreamRequestHandler):
    encrypt_table = string.maketrans('', '')[::-1]

    def decode(self, data):
        return data.translate(self.encrypt_table)

    def encode(self, data):
        return data.translate(self.encrypt_table)

    def handle_tcp(self, sock, remote):
        try:
            fdset = [sock, remote]
            while True:
                r, w, e = select.select(fdset, [], [])
                if sock in r:
                    if remote.send(self.encode(sock.recv(4096))) <= 0:
                        break
                if remote in r:
                    if sock.send(self.decode(remote.recv(4096))) <= 0:
                        break
        finally:
            sock.close()
            remote.close()

    def handle(self):
        sock = self.connection
        remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            host = config.get('720Proxy', 'server_host')
            port = int(config.get('720Proxy', 'server_socks_port'))
            remote.connect((host, port))
        except socket.error:
            print "Failed to connect to server %s:%d. If this continues to happen, this server may have failed, consider using other servers instead. "%(host,port)
            return
        token = config.get('720Proxy', 'token').strip()
        buffer = struct.pack('!BB', 1, len(token)) + token
        remote.send(self.encode(buffer+sock.recv(4096)))
        reply = remote.recv(1)
        if reply == '\x23':
            self.handle_tcp(sock, remote)
        else:
            sock.close()
            remote.close()


loadConfig()

if not config.get('720Proxy', 'token'):
    login()
else:
    print "Saved credential loaded"

HOST, PORT = "localhost", int(config.get('720Proxy', 'socksPort'))

# Create the server, binding to localhost on port 9999
server = SocketServer.ThreadingTCPServer((HOST, PORT), ProxyTCPHandler)
print "SOCKS V5 proxy started on %s port %d" % (HOST,PORT)
server.serve_forever()
server.server_close()