import socket
import threading
import datetime
import os
import signal
import sys
import csv

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False
    print("[WARN] matplotlib not found — graphs disabled.")
    print("       Fix: sudo apt install python3-matplotlib -y")

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════
HOST         = '0.0.0.0'
PORT         = 5000
LOG_FILE     = 'server_log.csv'
HISTORY_FILE = 'chat_history.csv'
PERF_CSV     = 'performance_results.csv'
GRAPHS_DIR   = 'graphs'

# ═══════════════════════════════════════════════════════════════
#  SHARED STATE
# ═══════════════════════════════════════════════════════════════
# clients dict: { conn: { username, ip, port, login_time, status } }
clients      = {}
clients_lock = threading.Lock()
server_socket = None

# Server-side statistics
stats = {
    'total_connections' : 0,
    'messages_processed': 0,
    'broadcast_messages': 0,
    'private_messages'  : 0,
}
stats_lock = threading.Lock()

# ═══════════════════════════════════════════════════════════════
#  TIMESTAMP HELPER
# ═══════════════════════════════════════════════════════════════
def ts():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def ts_short():
    return datetime.datetime.now().strftime('%H:%M:%S')

# ═══════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════
def log_event(event, username, client_ip):
    """Log CONNECTED / DISCONNECTED to server_log.csv."""
    line = f"{ts_short()},{event},{username},{client_ip}"
    print(f"[LOG] {line}")
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def log_history(sender, receiver, msg_type, message):
    """
    Append one row to chat_history.csv.
    msg_type: 'broadcast' or 'private'
    receiver: 'ALL' for broadcast, username for private
    """
    write_header = not os.path.exists(HISTORY_FILE)
    with open(HISTORY_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(['timestamp', 'sender', 'receiver',
                             'message_type', 'message'])
        writer.writerow([ts(), sender, receiver, msg_type, message])

def get_last_messages(username, n=5):
    """Return last n messages sent BY username from chat_history.csv."""
    if not os.path.exists(HISTORY_FILE):
        return []
    rows = []
    with open(HISTORY_FILE, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['sender'] == username:
                rows.append(row)
    return rows[-n:]

# ═══════════════════════════════════════════════════════════════
#  SEND HELPERS
# ═══════════════════════════════════════════════════════════════
def send_to(conn, message):
    """Send a message to a single connection safely."""
    try:
        conn.sendall(message.encode())
    except Exception:
        pass

def broadcast(message, sender_conn=None):
    """Send message to ALL clients except sender."""
    with clients_lock:
        for conn in list(clients.keys()):
            if conn != sender_conn:
                send_to(conn, message)

def send_private(sender_username, target_username, message, sender_conn):
    """
    Route a private message to target_username only.
    Returns True if delivered, False if user not found.
    """
    with clients_lock:
        target_conn = None
        for conn, info in clients.items():
            if info['username'] == target_username:
                target_conn = conn
                break

    if target_conn is None:
        send_to(sender_conn,
                f"[SERVER] User '{target_username}' not found or offline.\n")
        return False

    pm = f"[PM from {sender_username}] {message}\n"
    send_to(target_conn, pm)
    # Echo to sender so they see their own PM
    send_to(sender_conn,
            f"[PM to {target_username}] {message}\n")
    return True

# ═══════════════════════════════════════════════════════════════
#  /list COMMAND
# ═══════════════════════════════════════════════════════════════
def build_user_list():
    """Return a formatted string of all online users."""
    with clients_lock:
        if not clients:
            return "[SERVER] No users currently online.\n"
        lines = ["[SERVER] Online users:\n"]
        for info in clients.values():
            duration = datetime.datetime.now() - info['login_time']
            mins = int(duration.total_seconds() // 60)
            lines.append(
                f"  • {info['username']}  "
                f"({info['ip']}:{info['port']})  "
                f"online {mins}m\n"
            )
        return "".join(lines)

# ═══════════════════════════════════════════════════════════════
#  SERVER STATISTICS
# ═══════════════════════════════════════════════════════════════
def build_stats():
    with clients_lock:
        online = len(clients)
    with stats_lock:
        s = stats.copy()
    return (
        f"[SERVER STATS]\n"
        f"  Connected users    : {online}\n"
        f"  Total connections  : {s['total_connections']}\n"
        f"  Messages processed : {s['messages_processed']}\n"
        f"  Broadcast messages : {s['broadcast_messages']}\n"
        f"  Private messages   : {s['private_messages']}\n"
    )

# ═══════════════════════════════════════════════════════════════
#  GRAPH GENERATION  (Task 7) — called on CTRL+C
# ═══════════════════════════════════════════════════════════════
def generate_graphs():
    if not MATPLOTLIB_OK:
        print("[GRAPH] matplotlib not available.")
        return
    if not os.path.exists(PERF_CSV):
        print("[GRAPH] performance_results.csv not found.")
        return

    clients_list    = []
    avg_delay_list  = []
    throughput_list = []
    broadcast_list  = []
    private_list    = []

    with open(PERF_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            clients_list.append(int(row['clients']))
            avg_delay_list.append(float(row['avg_delay_ms']))
            throughput_list.append(float(row['throughput_msgs_per_sec']))
            broadcast_list.append(int(row['broadcast_messages']))
            private_list.append(int(row['private_messages']))

    if not clients_list:
        print("[GRAPH] CSV empty — no graphs.")
        return

    os.makedirs(GRAPHS_DIR, exist_ok=True)

    # ── Graph 1: Clients vs Average Delivery Time ─────────────
    plt.figure(figsize=(8, 5))
    plt.plot(clients_list, avg_delay_list,
             marker='o', color='royalblue', linewidth=2.5,
             markersize=9, label='Avg Delivery Time')
    plt.fill_between(clients_list, avg_delay_list, alpha=0.12, color='royalblue')
    for x, y in zip(clients_list, avg_delay_list):
        plt.annotate(f'{y:.2f} ms', (x, y),
                     textcoords='offset points', xytext=(0, 10), ha='center')
    plt.title('Number of Clients vs Average Delivery Time',
              fontsize=13, fontweight='bold')
    plt.xlabel('Number of Clients', fontsize=12)
    plt.ylabel('Average Delivery Time (ms)', fontsize=12)
    plt.xticks(clients_list)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f'{GRAPHS_DIR}/clients_vs_delay.png', dpi=150)
    plt.close()
    print(f"[GRAPH] Saved: clients_vs_delay.png")

    # ── Graph 2: Clients vs Throughput ───────────────────────
    plt.figure(figsize=(8, 5))
    plt.plot(clients_list, throughput_list,
             marker='s', color='seagreen', linewidth=2.5,
             markersize=9, label='Throughput')
    plt.fill_between(clients_list, throughput_list, alpha=0.12, color='seagreen')
    for x, y in zip(clients_list, throughput_list):
        plt.annotate(f'{y:.1f} m/s', (x, y),
                     textcoords='offset points', xytext=(0, 10), ha='center')
    plt.title('Number of Clients vs Throughput',
              fontsize=13, fontweight='bold')
    plt.xlabel('Number of Clients', fontsize=12)
    plt.ylabel('Throughput (msgs/sec)', fontsize=12)
    plt.xticks(clients_list)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f'{GRAPHS_DIR}/clients_vs_throughput.png', dpi=150)
    plt.close()
    print(f"[GRAPH] Saved: clients_vs_throughput.png")

    # ── Graph 3: Broadcast vs Private messages ────────────────
    x      = np.arange(len(clients_list))
    width  = 0.35
    labels = [f"{c} clients" for c in clients_list]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar(x - width/2, broadcast_list, width,
                   label='Broadcast', color='royalblue', alpha=0.85)
    bars2 = ax.bar(x + width/2, private_list, width,
                   label='Private', color='tomato', alpha=0.85)

    ax.set_title('Broadcast Messages vs Private Messages',
                 fontsize=13, fontweight='bold')
    ax.set_xlabel('Experiment', fontsize=12)
    ax.set_ylabel('Message Count', fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.5, axis='y')

    for bar in bars1:
        ax.annotate(f'{int(bar.get_height())}',
                    xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                    xytext=(0, 3), textcoords='offset points', ha='center')
    for bar in bars2:
        ax.annotate(f'{int(bar.get_height())}',
                    xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                    xytext=(0, 3), textcoords='offset points', ha='center')

    plt.tight_layout()
    plt.savefig(f'{GRAPHS_DIR}/message_type_distribution.png', dpi=150)
    plt.close()
    print(f"[GRAPH] Saved: message_type_distribution.png")
    print("[GRAPH] All 3 graphs generated successfully!")

# ═══════════════════════════════════════════════════════════════
#  GRACEFUL SHUTDOWN
# ═══════════════════════════════════════════════════════════════
def shutdown(sig, frame):
    print("\n[SERVER] Shutting down — generating graphs...")
    generate_graphs()
    if server_socket:
        server_socket.close()
    print("[SERVER] Done. Goodbye.")
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)

# ═══════════════════════════════════════════════════════════════
#  CLIENT HANDLER THREAD
# ═══════════════════════════════════════════════════════════════
def handle_client(conn, addr):
    client_ip   = addr[0]
    client_port = addr[1]
    username    = None

    try:
        # ── 1. Username registration ──────────────────────────
        send_to(conn, "ENTER_USERNAME\n")
        data = conn.recv(1024)
        if not data:
            conn.close()
            return
        username = data.decode().strip()

        login_time = datetime.datetime.now()

        with clients_lock:
            clients[conn] = {
                'username'  : username,
                'ip'        : client_ip,
                'port'      : client_port,
                'login_time': login_time,
                'status'    : 'online',
            }

        with stats_lock:
            stats['total_connections'] += 1

        log_event("CONNECTED", username, client_ip)

        # ── 2. Reconnect replay — show last 5 messages ────────
        history = get_last_messages(username, n=5)
        if history:
            replay  = f"[SERVER] Welcome back {username}! Your last {len(history)} message(s):\n"
            for row in history:
                replay += (f"  [{row['timestamp']}] "
                           f"[{row['message_type'].upper()}] "
                           f"→{row['receiver']}: {row['message']}\n")
            send_to(conn, replay)
        else:
            send_to(conn, f"[SERVER] Welcome {username}! Connected to chat.\n")

        # ── 3. Announce join to all others ────────────────────
        broadcast(f"[SERVER] {username} has joined the chat.\n",
                  sender_conn=conn)

        # ── 4. Message loop ───────────────────────────────────
        while True:
            data = conn.recv(4096)
            if not data:
                break

            message = data.decode().strip()

            if not message:
                continue

            # ── /quit ─────────────────────────────────────────
            if message == '/quit':
                break

            # ── PERF: echo back for timing measurement ────────
            if message.startswith('PERF:'):
                send_to(conn, f"ACK:{message}\n")
                with stats_lock:
                    stats['messages_processed'] += 1
                    stats['broadcast_messages'] += 1
                continue

            # ── /list — show online users ─────────────────────
            if message.strip() == '/list':
                send_to(conn, build_user_list())
                continue

            # ── /stats — server statistics ────────────────────
            if message.strip() == '/stats':
                send_to(conn, build_stats())
                continue

            # ── /msg <username> <message> — private message ───
            if message.startswith('/msg '):
                parts = message.split(' ', 2)
                if len(parts) < 3:
                    send_to(conn,
                            "[SERVER] Usage: /msg <username> <message>\n")
                    continue
                target_user = parts[1]
                pm_text     = parts[2]

                delivered = send_private(username, target_user,
                                         pm_text, conn)
                if delivered:
                    log_history(username, target_user, 'private', pm_text)
                    with stats_lock:
                        stats['messages_processed'] += 1
                        stats['private_messages']   += 1
                continue

            # ── Normal broadcast message ──────────────────────
            formatted = f"[{username}] {message}\n"
            print(f"  {formatted}", end='')

            log_history(username, 'ALL', 'broadcast', message)

            with stats_lock:
                stats['messages_processed'] += 1
                stats['broadcast_messages'] += 1

            # Echo to sender + broadcast to others
            send_to(conn, formatted)
            broadcast(formatted, sender_conn=conn)

    except Exception as e:
        print(f"[ERROR] {addr}: {e}")

    finally:
        with clients_lock:
            if conn in clients:
                del clients[conn]
        if username:
            log_event("DISCONNECTED", username, client_ip)
            broadcast(f"[SERVER] {username} has left the chat.\n")
        conn.close()

# ═══════════════════════════════════════════════════════════════
#  MAIN SERVER LOOP
# ═══════════════════════════════════════════════════════════════
def start_server():
    global server_socket

    # Clear old event log on fresh start (keep chat_history.csv)
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(10)

    print("=" * 55)
    print("  Enhanced Multi-Client Chat Server — Assignment 5")
    print(f"  Listening on port {PORT}")
    print("  Commands available to clients:")
    print("    /list               — show online users")
    print("    /msg <user> <text>  — private message")
    print("    /stats              — server statistics")
    print("    /quit               — disconnect")
    print("  Press CTRL+C to stop and generate graphs")
    print("=" * 55)

    while True:
        try:
            conn, addr = server_socket.accept()
            print(f"[SERVER] New connection from {addr}")
            t = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True
            )
            t.start()
        except OSError:
            break

if __name__ == '__main__':
    start_server()
