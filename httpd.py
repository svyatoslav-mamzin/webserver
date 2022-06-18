# -*- coding: utf-8 -*-
import mimetypes
import socket
import threading
import sys
import signal
import logging
import time
import os
import uuid
from urllib.parse import unquote
import argparse

logging.basicConfig(format='[%(asctime)s] %(levelname).1s %(message)s',
                    datefmt='%Y.%m.%d %H:%M:%S',
                    level=logging.INFO)

HOST = '127.0.0.1'
PORT = 8080
DOCUMENT_ROOT = 'www'

OK = 200
NOT_FOUND = 404
FORBIDDEN = 403
BAD_REQUEST = 400
NOT_ALLOWED = 405
INTERNAL_SERVER_ERROR = 500
HTTP_VERSION_NOT_SUPPORTED = 505
HTML_ERROR = """<html>
<head>
<meta charset="UTF-8"> 
<title>{status} - {text}</title>
</head>
<body>
<h1>¯\_(ツ)_/¯</h1>
<h2>{status}</h2>
<p>{text}</p>
</body>
</html>
"""


class Server:
    """
    Simply TCP Server:
    request: "My name is Svyatoslav"
    response: "Hello, Svyatoslav"
    """
    def __init__(self, host, port, workers):
        self.host = host
        self.port = port
        self.read_size = 1024
        self.workers = workers
        self.opened_threads = []

    def start(self):
        """ Attempts to aquire the socket and launch the server """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        logging.info(f"Launching HTTP server on {self.host} : {self.port}")
        try:
            self.sock.bind((self.host, self.port))
        except Exception:
            logging.info(f"ERROR: Failed to acquire sockets for port {self.port}")
            logging.info("Try running the Server in a privileged user mode.")
            self.shutdown()
            sys.exit(1)

        logging.info(f"Server successfully acquired the socket with port: {self.port}")
        logging.info("Press Ctrl+C to shut down the server and exit.")
        logging.debug('STARTING WORKERS')
        for _ in range(self.workers):
            worker_key = f'WORKER {uuid.uuid1()}'
            logging.info(f'Starting worker with key: {worker_key}')
            t = threading.Thread(target=self._listen, args=(worker_key,))
            t.start()
            self.opened_threads.append(t)
        logging.debug('WORKERS STARTED')

    def _listen(self, worker_key):
        self.sock.listen(5)
        threading.currentThread()
        while True:
            logging.debug(f'{worker_key}: ACCEPTING')
            try:
                client, address = self.sock.accept()
            except OSError:
                return False
            logging.debug(f'{worker_key}: ADDRESS: {address}')
            logging.debug(f'{worker_key}: SET TIMEOUT')
            client.settimeout(10)
            self._listen_to_client(client, address, worker_key, ' ')

    def _listen_to_client(self, client, address, worker_key,  thread_key):
        logging.debug(f'{worker_key} : THREAD {thread_key} : STARTED NEW THREAD FOR {address}')
        try:
            logging.debug(f'{worker_key} : THREAD {thread_key} : GETTING DATA')
            data = client.recv(self.read_size)
        except OSError:
            logging.info(f'{worker_key} : THREAD {thread_key} : CLIENT DISCONNECTED, EXITING')
            client.close()
        logging.debug(f'{worker_key} : THREAD {thread_key} : DATA IS: {data}')
        if data:
            response = self.get_response(data)
            client.sendall(response)
            logging.info(f'{worker_key} : THREAD {thread_key} : RESPONSE SENDED, EXITING')
            client.close()
        else:
            raise socket.error('Client disconnected')

    def get_response(self, data: bytes) -> bytes:
        data = data.decode()
        if ' is ' in data:
            name = data.split('is ')[-1]
            response = f'Hello, {name}!'
            return response.encode()
        else:
            return b'Unknown hello string'

    def shutdown(self):
        """ Shut down the server """
        exit_code = 0
        try:
            logging.info("Shutting down the server")
            self.sock.shutdown(socket.SHUT_RDWR)
            for th in threading.enumerate():
                if th != threading.main_thread():
                    logging.info(f"JOINING THREAD{th.name}")
                    th.join(2)
        except Exception as e:
            logging.info(f"Warning: could not shut down the socket. Maybe it was already closed? {e}")
            exit_code = 1
        finally:
            sys.exit(exit_code)


def get_html_from_path(path):
    html = b''
    try:
        logging.debug(f'TRY OPEN FILE: {path}')
        with open(path, 'rb') as f:
            html = f.read()
    except Exception as e:
        logging.debug(f"EXCEPTION {e}")
    return html


def gen_headers(code, content_length, content_type):
    """ Generates HTTP response Headers."""
    http_statuses = {
        200: 'HTTP/1.1 200 OK\r\n',
        404: 'HTTP/1.1 404 Not Found\r\n',
        405: 'HTTP/1.1 405 Method Not Allowed\r\n',
        403: 'HTTP/1.1 403 Forbidden\r\n'
    }

    return f"{http_statuses[code]}" \
           f"Date: {time.strftime('%a, %d %b %Y %H:%M:%S', time.localtime())}\r\n" \
           f"Server: My-HTTP-Server\r\n" \
           f"Connection: close\r\n" \
           f"Content-Length: {content_length}\r\n" \
           f"Content-Type: {content_type}\n\n"


class HTTPServer(Server):
    def __init__(self, host, port, workers, document_root):
        self.document_root = document_root
        self.delimiter = b'\r\n'
        self.ender = b'\r\n\r\n'
        self.close_connection = True
        super().__init__(host, port, workers)

    def _get_headers(self, data):
        """Only \r\n delimiter syntax is supported
           returns tuple:
                headers: dict (empty if error while parsing headers
                error: tuple(error_code, error_str) (empty if parsed without an error)
        """
        headers = dict()
        headersline = str(data, 'iso-8859-1')
        headersline = headersline.rstrip('\r\n')
        headerslist = headersline.split('\r\n')
        try:
            firstline, add_headers = headerslist[0], headerslist[1:]
            words = firstline.split()
        except Exception:
            return dict(), (BAD_REQUEST, "Bad request syntax (%r)" % headersline)
        command, path, version = '', '', ''
        if len(words) == 3:
            command, path, version = words
        elif len(words) == 2:
            command, path = words

        headers['command'] = command
        headers['path'] = path
        headers['version'] = version
        for line in add_headers:
            key, value = line.split(': ')
            headers[key] = value
        logging.debug(f'HEADERS: {headers}')

        if headers['version']:
            version = headers['version']
            try:
                if version[:5] != 'HTTP/':
                    raise ValueError
                base_version_number = version.split('/', 1)[1]
                version_number = base_version_number.split(".")
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
            except (ValueError, IndexError):
                return dict(), (BAD_REQUEST, "Bad request version (%r)" % version)
            if version_number >= (2, 0):
                return dict(), (HTTP_VERSION_NOT_SUPPORTED, "Invalid HTTP version (%s)" % base_version_number)
        if headers['command'] not in ['GET', 'HEAD']:
            return dict(), (NOT_ALLOWED, "Method not allowed: (%r)" % headers['command'])

        return headers, tuple()

    def _resolve_path(self, path: str) -> tuple:
        logging.debug(f'PATH GETTED {path}')
        query = ''
        if '?' in path:
            path, query = path.split('?')
        if '../' in path:
            return '', ''
        if '%' in path:
            path = unquote(path)
        if path == '/':
            path = os.path.join(self.document_root, 'index.html')
        else:
            path = self.document_root + path
        if os.path.isdir(path):
            path = os.path.join(path, 'index.html')  # 'htm' extension is not supported
        logging.debug(f'RESOLVED PATH: {path}')
        return path, query

    def get_response(self, data):
        headers, error = self._get_headers(data)
        if error:
            status, text = error
            html_err = HTML_ERROR.format(status=status, text=text).encode() + b'\r\n\r\n'
            return gen_headers(status, len(html_err), 'text/html').encode() + html_err
        path, query = self._resolve_path(headers['path'])
        content_type, _ = mimetypes.guess_type(path)

        if headers['command'] == 'HEAD':
            return gen_headers(OK, len(get_html_from_path(path)), content_type).encode() + b'\r\n\r\n'

        html = get_html_from_path(path)
        if html:
            return gen_headers(OK, len(html), content_type).encode() + html

        html_err = HTML_ERROR.format(status=NOT_FOUND, text='Page not found').encode()
        return gen_headers(NOT_FOUND, len(html_err), 'text/html').encode() + html_err


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--ip', default=HOST)
    parser.add_argument('-p', '--port', default=PORT, type=int)
    parser.add_argument('-w', '--workers', default=4, type=int)
    parser.add_argument('-r', '--documentroot', default=DOCUMENT_ROOT)
    return parser


def get_config() -> dict:
    parser = create_parser()
    namespace = parser.parse_args()
    return {
        'host': namespace.ip,
        'port': namespace.port,
        'workers': namespace.workers,
        'document_root': namespace.documentroot,
    }


if __name__ == '__main__':
    config = get_config()
    logging.info("Starting web server")
    server = HTTPServer(**config)  # construct server object
    # shut down on ctrl+c
    signal.signal(signal.SIGINT, server.shutdown)
    server.start()  # aquire the socket
