import socket
import threading
import SocketServer

class BR24TCPRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        data = self.request.recv(1024)
        tokens = data.split(":::")
        command = tokens[0]
        if command == 'ST':
            

class BR24TCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):
        SocketServer.TCPServer.__init__( self, server_address, RequestHandlerClass)
        self.br = BR24_driver.br24()
        self.br.start()

def client(ip, port, message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))
    try:
        sock.sendall(message)
        response = sock.recv(1024)
        print "Received: {}".format(response)
    finally:
        sock.close()

if __name__ == "__main__":
    # Port 0 means to select an arbitrary unused port
    HOST, PORT = socket.gethostname(), 9090
    server = BR24TCPServer((HOST, PORT), BR24TCPRequestHandler)
    try:
        print "Stopping radar server at %s"%((HOST,PORT))
        server.serve_forever()
    except KeyboardInterrupt:
        print "Stopping radar server.."
        br.stop()
