import socket
import threading
import datetime
import os
import signal
import sys
import csv
import hashlib
import time
import json
import psutil

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

with open('config.json', 'r') as f:
    config = json.load(f)

HOST = '0.0.0.0'
PORT = config.get('port', 5000)
INACTIVITY_TIMEOUT = config.get('inactivity_timeout', 300.0)
LOCKOUT_TIME = config.get('lockout_time', 60)
MAX_FAILED = config.get('max_failed_logins', 5)
PERF_INTERVAL = config.get('perf_log_interval', 5)

LOG_FILE = 'server_log.csv'
HISTORY_FILE = 'chat_history.csv'
PERF_CSV = 'performance_results.csv'
GRAPHS_DIR = 'graphs'
USERS_FILE = 'users.csv'
SECURITY_LOG = 'security_log.txt'

clients = {}
clients_lock = threading.Lock()
server_socket = None
running = True

stats = {
    'total_connections': 0,
    'messages_processed': 0,
    'broadcast_messages': 0,
    'private_messages': 0,
    'total_delay_ms': 0.0
}
stats_lock = threading.Lock()

users_db = {}
failed_logins = {}

def ts():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def ts_short():
    return datetime.datetime.now().strftime('%H:%M:%S')

def log_security(event, username, ip_addr):
    line = f"[{ts()}] {event} | User: {username} | IP: {ip_addr}\n"
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

def send_to(conn, message):
    try:
        conn.sendall(message.encode())
    except socket.error:
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
            return "[SERVER] No users online.\n"
        lines = ["[SERVER] Online users:\n"]
        for info in clients.values():
            duration = datetime.datetime.now() - info['login_time']
            mins = int(duration.total_seconds() // 60)
            lines.append(f"  - {info['username']} ({info['ip']}) online {mins}m\n")
        return "".join(lines)

def monitor_performance():
    if not os.path.exists(PERF_CSV):
        with open(PERF_CSV, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'clients', 'cpu_percent', 'memory_percent', 'throughput_msg_per_sec', 'avg_delay_ms'])
    
    while running:
        time.sleep(PERF_INTERVAL)
        with clients_lock:
            active_clients = len(clients)
        with stats_lock:
            msgs = stats['messages_processed']
            total_delay = stats['total_delay_ms']
            stats['messages_processed'] = 0
            stats['total_delay_ms'] = 0.0

        throughput = msgs / PERF_INTERVAL
        avg_delay = (total_delay / msgs) if msgs > 0 else 0.0
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent

        with open(PERF_CSV, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([ts_short(), active_clients, cpu, mem, throughput, avg_delay])

def generate_graphs():
    if not MATPLOTLIB_OK or not os.path.exists(PERF_CSV):
        return
    
    os.makedirs(GRAPHS_DIR, exist_ok=True)
    times, clients_data, cpu_data, mem_data, tput_data = [], [], [], [], []
    
    with open(PERF_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            times.append(row['timestamp'])
            clients_data.append(int(row['clients']))
            cpu_data.append(float(row['cpu_percent']))
            mem_data.append(float(row['memory_percent']))
            tput_data.append(float(row['throughput_msg_per_sec']))

    if not times:
        return

    plt.figure(figsize=(10, 5))
    plt.plot(times, cpu_data, label='CPU (%)', color='red')
    plt.plot(times, mem_data, label='Memory (%)', color='blue')
    plt.title('System Resource Usage Over Time')
    plt.xlabel('Time')
    plt.ylabel('Percentage')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f'{GRAPHS_DIR}/resource_usage.png')
    plt.close()

    plt.figure(figsize=(10, 5))
    plt.plot(times, tput_data, label='Throughput (msgs/sec)', color='green')
    plt.title('Server Throughput')
    plt.xlabel('Time')
    plt.ylabel('Messages / Second')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f'{GRAPHS_DIR}/throughput.png')
    plt.close()

def shutdown(sig, frame):
    global running
    print("\n[SERVER] Initiating graceful shutdown...")
    running = False
    broadcast("[SERVER] Server is shutting down.\n")
    time.sleep(1)
    with clients_lock:
        for conn in list(clients.keys()):
            conn.close()
    if server_socket:
        server_socket.close()
    generate_graphs()
    print("[SERVER] Shutdown complete.")
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)

def handle_client(conn, addr):
    client_ip, client_port = addr
    username = None

    try:
        send_to(conn, "AUTH_REQUIRED\n")
        data = conn.recv(1024)
        if not data or len(data) > 256:
            return
        
        try:
            req_user, req_pass = data.decode().strip().split('\0', 1)
        except ValueError:
            send_to(conn, "AUTH_FAIL:Invalid format\n")
            return

        if not req_user.isalnum() or len(req_user) < 2 or not req_pass:
            send_to(conn, "AUTH_FAIL:Invalid format.\n")
            log_security("INVALID_INPUT_REJECTED", req_user, client_ip)
            return

        if req_user in failed_logins:
            attempts, lock_time = failed_logins[req_user]
            if attempts >= MAX_FAILED:
                if time.time() - lock_time < LOCKOUT_TIME:
                    send_to(conn, "AUTH_FAIL:Account locked. Try again later.\n")
                    log_security("LOCKOUT_ACTIVE", req_user, client_ip)
                    return
                else:
                    failed_logins.pop(req_user)

        pwd_hash = hashlib.sha256(req_pass.encode()).hexdigest()
        
        if req_user in users_db:
            if users_db[req_user] != pwd_hash:
                attempts = failed_logins.get(req_user, (0, 0))[0] + 1
                failed_logins[req_user] = (attempts, time.time())
                log_security("LOGIN_FAILED", req_user, client_ip)
                send_to(conn, f"AUTH_FAIL:Incorrect credentials. Attempt {attempts}/{MAX_FAILED}\n")
                return
        else:
            users_db[req_user] = pwd_hash
            save_user(req_user, pwd_hash)
            log_security("USER_REGISTERED", req_user, client_ip)

        with clients_lock:
            for c, info in clients.items():
                if info['username'] == req_user:
                    send_to(conn, "AUTH_FAIL:User already logged in.\n")
                    log_security("DUPLICATE_LOGIN", req_user, client_ip)
                    return
            
            username = req_user
            clients[conn] = {
                'username': username,
                'ip': client_ip,
                'port': client_port,
                'login_time': datetime.datetime.now()
            }

        if username in failed_logins:
            failed_logins.pop(username)

        with stats_lock:
            stats['total_connections'] += 1

        log_security("LOGIN_SUCCESS", username, client_ip)
        log_event("CONNECTED", username, client_ip)
        send_to(conn, f"AUTH_SUCCESS\n[SERVER] Welcome {username}!\n")
        broadcast(f"[SERVER] {username} joined.\n", sender_conn=conn)
        conn.settimeout(INACTIVITY_TIMEOUT)

        while running:
            start_time = time.time()
            data = conn.recv(4096)
            if not data:
                break
            
            if len(data) > 2048:
                send_to(conn, "[SERVER] Message too large.\n")
                continue

            message = data.decode().strip()
            if not message:
                continue

            if message == '/quit':
                break

            process_time = (time.time() - start_time) * 1000

            if message == '/list':
                send_to(conn, build_user_list())
            elif message.startswith('/msg '):
                parts = message.split(' ', 2)
                if len(parts) >= 3:
                    if send_private(username, parts[1], parts[2], conn):
                        with stats_lock:
                            stats['messages_processed'] += 1
                            stats['private_messages'] += 1
                            stats['total_delay_ms'] += process_time
            else:
                formatted = f"[{username}] {message}\n"
                with stats_lock:
                    stats['messages_processed'] += 1
                    stats['broadcast_messages'] += 1
                    stats['total_delay_ms'] += process_time
                send_to(conn, formatted)
                broadcast(formatted, sender_conn=conn)

    except socket.timeout:
        log_security("SESSION_TIMEOUT", username, client_ip)
        send_to(conn, "[SERVER] Disconnected due to inactivity.\n")
    except (ConnectionResetError, BrokenPipeError):
        pass 
    except Exception as e:
        print(f"[ERROR] {addr}: {e}")
    finally:
        with clients_lock:
            if conn in clients:
                del clients[conn]
        if username:
            log_event("DISCONNECTED", username, client_ip)
            log_security("LOGOUT", username, client_ip)
            broadcast(f"[SERVER] {username} left.\n")
        conn.close()

def start_server():
    global server_socket
    load_users()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(config.get('max_clients', 50))

    threading.Thread(target=monitor_performance, daemon=True).start()
    print(f"[SERVER] Running securely on {HOST}:{PORT}")

    while running:
        try:
            conn, addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except OSError:
            break

if __name__ == '__main__':
    start_server()
