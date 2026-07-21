import socket
import threading
import datetime
import os
import signal
import sys
import csv
import hashlib
import time

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

HOST = '0.0.0.0'
PORT = 5000
LOG_FILE = 'server_log.csv'
HISTORY_FILE = 'chat_history.csv'
PERF_CSV = 'performance_results.csv'
GRAPHS_DIR = 'graphs'
USERS_FILE = 'users.csv'
SECURITY_LOG = 'security_log.txt'

clients = {}
clients_lock = threading.Lock()
server_socket = None

stats = {
    'total_connections': 0,
    'messages_processed': 0,
    'broadcast_messages': 0,
    'private_messages': 0,
}
stats_lock = threading.Lock()

# Security State
users_db = {}
failed_logins = {}
LOCKOUT_TIME = 60
INACTIVITY_TIMEOUT = 300.0

def ts():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def ts_short():
    return datetime.datetime.now().strftime('%H:%M:%S')

def log_security(event, username, ip_addr):
    line = f"[{ts()}] {event} | User: {username} | IP: {ip_addr}\n"
    print(f"[SECURITY] {line.strip()}")
    with open(SECURITY_LOG, 'a') as f:
        f.write(line)

def load_users():
    if not os.path.exists(USERS_FILE):
        return
    with open(USERS_FILE, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) == 2:
                users_db[row[0]] = row[1]

def save_user(username, pwd_hash):
    with open(USERS_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([username, pwd_hash])

def log_event(event, username, client_ip):
    line = f"{ts_short()},{event},{username},{client_ip}"
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def log_history(sender, receiver, msg_type, message):
    write_header = not os.path.exists(HISTORY_FILE)
    with open(HISTORY_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(['timestamp', 'sender', 'receiver', 'message_type', 'message'])
        writer.writerow([ts(), sender, receiver, msg_type, message])

def send_to(conn, message):
    try:
        conn.sendall(message.encode())
    except Exception:
        pass

def broadcast(message, sender_conn=None):
    with clients_lock:
        for conn in list(clients.keys()):
            if conn != sender_conn:
                send_to(conn, message)

def send_private(sender_username, target_username, message, sender_conn):
    with clients_lock:
        target_conn = None
        for conn, info in clients.items():
            if info['username'] == target_username:
                target_conn = conn
                break

    if target_conn is None:
        send_to(sender_conn, f"[SERVER] User '{target_username}' not found or offline.\n")
        return False

    send_to(target_conn, f"[PM from {sender_username}] {message}\n")
    send_to(sender_conn, f"[PM to {target_username}] {message}\n")
    return True

def build_user_list():
    with clients_lock:
        if not clients:
            return "[SERVER] No users currently online.\n"
        lines = ["[SERVER] Online users:\n"]
        for info in clients.values():
            duration = datetime.datetime.now() - info['login_time']
            mins = int(duration.total_seconds() // 60)
            lines.append(f"  • {info['username']} ({info['ip']}) online {mins}m\n")
        return "".join(lines)

def build_stats():
    with clients_lock:
        online = len(clients)
    with stats_lock:
        s = stats.copy()
    return (f"[SERVER STATS]\n  Connected users: {online}\n"
            f"  Messages processed: {s['messages_processed']}\n")

def shutdown(sig, frame):
    print("\n[SERVER] Shutting down...")
    if server_socket:
        server_socket.close()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)

def handle_client(conn, addr):
    client_ip, client_port = addr
    username = None

    try:
        send_to(conn, "AUTH_REQUIRED\n")
        data = conn.recv(1024)
        if not data or len(data) > 256:
            conn.close()
            return
        
        try:
            req_user, req_pass = data.decode().strip().split('\0', 1)
        except ValueError:
            send_to(conn, "AUTH_FAIL:Invalid format\n")
            conn.close()
            return

        if not req_user.isalnum() or len(req_user) < 2 or not req_pass:
            send_to(conn, "AUTH_FAIL:Invalid username or password format.\n")
            log_security("INVALID_INPUT_REJECTED", req_user, client_ip)
            conn.close()
            return

        if req_user in failed_logins:
            attempts, lock_time = failed_logins[req_user]
            if attempts >= 5:
                if time.time() - lock_time < LOCKOUT_TIME:
                    send_to(conn, "AUTH_FAIL:Account locked. Try again later.\n")
                    log_security("LOCKOUT_ACTIVE_REJECTED", req_user, client_ip)
                    conn.close()
                    return
                else:
                    failed_logins.pop(req_user)

        pwd_hash = hashlib.sha256(req_pass.encode()).hexdigest()
        
        if req_user in users_db:
            if users_db[req_user] != pwd_hash:
                attempts = failed_logins.get(req_user, (0, 0))[0] + 1
                failed_logins[req_user] = (attempts, time.time())
                log_security("LOGIN_FAILED", req_user, client_ip)
                send_to(conn, f"AUTH_FAIL:Incorrect credentials. Attempt {attempts}/5\n")
                conn.close()
                return
        else:
            users_db[req_user] = pwd_hash
            save_user(req_user, pwd_hash)
            log_security("USER_REGISTERED", req_user, client_ip)

        with clients_lock:
            for c, info in clients.items():
                if info['username'] == req_user:
                    send_to(conn, "AUTH_FAIL:User already logged in.\n")
                    log_security("DUPLICATE_LOGIN_REJECTED", req_user, client_ip)
                    conn.close()
                    return
            
            username = req_user
            clients[conn] = {
                'username': username,
                'ip': client_ip,
                'port': client_port,
                'login_time': datetime.datetime.now(),
                'status': 'online',
            }

        if username in failed_logins:
            failed_logins.pop(username)

        with stats_lock:
            stats['total_connections'] += 1

        log_security("LOGIN_SUCCESS", username, client_ip)
        log_event("CONNECTED", username, client_ip)
        
        send_to(conn, f"AUTH_SUCCESS\n[SERVER] Welcome {username}! Connected to secure chat.\n")
        broadcast(f"[SERVER] {username} has joined the chat.\n", sender_conn=conn)

        conn.settimeout(INACTIVITY_TIMEOUT)

        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break

                if len(data) > 2048:
                    send_to(conn, "[SERVER] Error: Message too large.\n")
                    log_security("OVERSIZED_MESSAGE_REJECTED", username, client_ip)
                    continue

                message = data.decode().strip()
                if not message:
                    continue

                if message == '/quit':
                    break

                if message.startswith('/'):
                    cmd = message.split()[0]
                    if cmd not in ['/quit', '/list', '/stats', '/msg']:
                        send_to(conn, f"[SERVER] Error: Unsupported command '{cmd}'.\n")
                        log_security("UNSUPPORTED_COMMAND_REJECTED", username, client_ip)
                        continue

                if message == '/list':
                    send_to(conn, build_user_list())
                    continue

                if message == '/stats':
                    send_to(conn, build_stats())
                    continue

                if message.startswith('/msg '):
                    parts = message.split(' ', 2)
                    if len(parts) < 3:
                        send_to(conn, "[SERVER] Usage: /msg <username> <message>\n")
                        continue
                    target_user, pm_text = parts[1], parts[2]
                    if send_private(username, target_user, pm_text, conn):
                        log_history(username, target_user, 'private', pm_text)
                        with stats_lock:
                            stats['messages_processed'] += 1
                            stats['private_messages'] += 1
                    continue

                formatted = f"[{username}] {message}\n"
                log_history(username, 'ALL', 'broadcast', message)
                
                with stats_lock:
                    stats['messages_processed'] += 1
                    stats['broadcast_messages'] += 1

                send_to(conn, formatted)
                broadcast(formatted, sender_conn=conn)

            except socket.timeout:
                log_security("SESSION_TIMEOUT", username, client_ip)
                send_to(conn, "[SERVER] Disconnected due to inactivity.\n")
                break

    except Exception as e:
        print(f"[ERROR] {addr}: {e}")

    finally:
        with clients_lock:
            if conn in clients:
                del clients[conn]
        if username:
            log_event("DISCONNECTED", username, client_ip)
            log_security("LOGOUT", username, client_ip)
            broadcast(f"[SERVER] {username} has left the chat.\n")
        conn.close()

def start_server():
    global server_socket
    load_users()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(10)

    print("=" * 55)
    print("  Secure TCP Chat Server — Assignment 7")
    print(f"  Listening on port {PORT}")
    print("=" * 55)

    while True:
        try:
            conn, addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except OSError:
            break

if __name__ == '__main__':
    start_server()
