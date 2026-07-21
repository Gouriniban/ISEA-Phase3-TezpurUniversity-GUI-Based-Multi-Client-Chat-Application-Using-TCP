<img width="758" height="490" alt="login_window" src="https://github.com/user-attachments/assets/74e4d1d4-c21b-4108-932a-0e7dfb5af13b" />
<img width="970" height="727" alt="connected" src="https://github.com/user-attachments/assets/11d1e25f-ee4e-438d-9dad-613fc4c28f54" />
# ISEA-Phase3-TezpurUniversity-GUI-Based-Multi-Client-Chat-Application-Using-TCP
# ISEA-Phase3-TezpurUniversity — Assignment 6

## GUI-Based Multi-Client Chat Application Using TCP

## Project Title
**Assignment 6: GUI-Based Multi-Client Chat Application Using TCP**

---![Uploading user_leave.png…]()


## Objective
Convert the terminal-based TCP chat application from Assignment 5 into a graphical desktop
application using Python's `tkinter` library. The assignment introduces GUI programming,
event-driven design, and multithreading in the context of a real networked application,
while reusing the existing server and socket communication logic without modification.

---

## Software Requirements

| Component | Version / Notes |
|-----------|-----------------|
| OS | Ubuntu 22.04 / 24.04 (or Mininet VM) |
| Python | 3.10 or higher |
| Mininet | 2.3.x (`sudo apt install mininet`) |
| tkinter | Included with Python (`python3-tk`) |
| matplotlib | For graph generation (`sudo apt install python3-matplotlib`) |
| Wireshark | For traffic capture (`sudo apt install wireshark`) |

No third-party Python packages are required for the chat application itself.

---

## Network Topology

```
sudo mn --topo single,5
```

```
         +----------+
         | Switch s1|
         +----+-----+
    _____|____|____|____
   |     |        |    |
  h1    h2       h3   h4   h5
Server  Client A  B    C    D
10.0.0.1 10.0.0.2 .3  .4   .5
```

| Host | Role | IP Address |
|------|------|------------|
| h1 | Chat Server | 10.0.0.1 |
| h2 | Client A | 10.0.0.2 |
| h3 | Client B | 10.0.0.3 |
| h4 | Client C | 10.0.0.4 |
| h5 | Client D | 10.0.0.5 |

Verify connectivity after starting Mininet:
```
mininet> nodes
mininet> net
mininet> pingall
```

---

## Execution Steps

### 1. Start Mininet
```bash
sudo mn --topo single,5
```

### 2. Open xterm windows
```
mininet> xterm h1 h2 h3 h4 h5
```

### 3. Start the server on h1
```bash
# In h1's terminal
python3 server.py
```

### 4. Start GUI clients on h2–h5
```bash
# In each client terminal (h2, h3, h4, h5)
python3 client_gui.py 10.0.0.1
```

### 5. Using the application
- Enter your **username** in the login window and click **Connect**
- Type a message and press **Enter** or click **Send ➤** to broadcast
- To send a **private message**: enter the target username in the *Private to:* field, then type your message and send
- Click a username in the **Online Users** panel to auto-fill the PM target
- Type `/list` to see online users, `/stats` for server statistics
- Click **Disconnect** or type `/quit` to exit

### 6. Stop the server and generate graphs
```
CTRL+C in the server terminal
```
Graphs are saved to `graphs/` directory automatically.

---

## Brief Description of the Implementation

### Server (`server.py`) — Reused from Assignment 5
The server is a multi-threaded TCP server listening on port 5000. A dedicated daemon thread
is spawned per client. A `threading.Lock` protects the shared clients dictionary. The server
supports:
- Username registration via `ENTER_USERNAME` handshake
- Broadcast messaging to all connected clients
- Private messaging via `/msg <target> <text>`
- Online user listing via `/list`
- Server statistics via `/stats`
- Chat history persistence in `chat_history.csv` with replay on reconnect
- Connection event logging to `server_log.csv`
- Graceful shutdown on CTRL+C with automatic performance graph generation

### Client GUI (`client_gui.py`) — New in Assignment 6
The GUI client is built with `tkinter` and structured into three classes:

**`ChatClient`** — pure networking layer, no GUI imports. Manages the TCP socket,
sends messages, and runs a background daemon thread (`_recv_loop`) for receiving.
Incoming messages are dispatched to the GUI via `root.after(0, callback)` — the only
thread-safe way to update tkinter from a non-main thread.

**`LoginWindow`** — the login screen. Validates that the username is non-empty,
at least 2 characters, and contains no spaces. Shows inline error/success messages.

**`ChatWindow`** — the main chat interface. Features:
- Scrollable, color-coded message area (yellow = server, blue = own, white = others,
  green = incoming PM, purple = outgoing PM)
- Private To entry field (empty = broadcast)
- Online Users listbox with click-to-PM auto-fill
- Commands reference sidebar (/list, /stats, /quit)
- Connection status indicator and status bar

**`App`** — entry point. Creates one `Tk` root window, starts with `LoginWindow`,
and replaces it with `ChatWindow` on successful connection (no second top-level window).

---

## Screenshots

| Screenshot | Description |
|-----------|-------------|
| `screenshots/login_window.png` | Login window with username entry |
| `screenshots/chat_window.png` | Main chat interface |
| `screenshots/ws_client_connection.png` | Wireshark — TCP handshake |
| `screenshots/ws_broadcast.png` | Wireshark — broadcast message stream |
| `screenshots/ws_private_msg.png` | Wireshark — private message routing |
| `screenshots/ws_disconnect.png` | Wireshark — FIN/ACK disconnection |

---

## File Structure

```
ISEA-Phase3-TezpurUniversity-Assignment6/
├── server.py               # TCP chat server (reused from Assignment 5)
├── client_gui.py           # tkinter GUI client
├── screenshots/            # Wireshark and application screenshots
├── graphs/                 # Auto-generated performance graphs (post-run)
├── report.pdf              # Assignment report
└── README.md               # This file
```

---

## Author
**Gouriniban Borphukan** | Roll No. CSB24032
B.Tech Computer Science & Engineering — Tezpur University
ISEA Phase 3 Internship
