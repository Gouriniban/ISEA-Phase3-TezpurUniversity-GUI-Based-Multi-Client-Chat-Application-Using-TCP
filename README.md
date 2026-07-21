# Secure GUI-Based Multi-Client Chat Application (TCP)

## Objective
To enhance a GUI-based multi-client TCP chat application by implementing practical security mechanisms including user authentication, secure password storage (SHA-256), duplicate login prevention, session management (timeouts), and input validation, while maintaining strict separation of networking logic and GUI code.

## Software Requirements
* **Language:** Python 3.x
* **GUI Library:** `tkinter` (Python Standard Library)
* **Networking/Security:** `socket`, `threading`, `hashlib`
* **Environment:** Mininet (Network Emulator)
* **Analysis Tool:** Wireshark (for packet capturing)
* **Operating System:** Ubuntu/Linux recommended

## Network Topology
The application is tested within a Mininet virtual network using a single-switch topology with 5 hosts:
* **h1:** Chat Server
* **h2:** Client A
* **h3:** Client B
* **h4:** Client C
* **h5:** Client D

## Execution Steps

1. **Start the Mininet Network:**
   Open a terminal and launch the topology:
   
   sudo mn --topo single,5

2. Start the Chat Server:
    Inside the Mininet CLI, run the server on host 1 (h1):

    mininet> h1 python3 server.py &

3.    Launch the Clients:
    Open terminal windows for the client hosts:

  mininet> xterm h2 h3 h4 h5

4.    Connect to the Chat:
    In each xterm window, execute the client GUI script using the server's IP address:

  python3 client_gui.py 10.0.0.1

    Note: On your first login, the application will automatically register your username and hash your password into the local database.

Brief Description of the Implementation

This project builds upon a foundational TCP chat client/server model by introducing robust application-layer security.

1. GUI & Threading: The client utilizes a tkinter desktop interface that handles background TCP socket I/O using daemon threads, ensuring the UI remains highly responsive without freezing during blocking operations.

2.  Authentication & Cryptography: The server intercepts incoming connections with an AUTH_REQUIRED protocol. Passwords are never transmitted back or stored in plain text; they are hashed using the hashlib.sha256() algorithm and saved locally in a users.csv database.

3.   Access Control & Session Management: Active sessions are monitored in a thread-safe dictionary to prevent duplicate concurrent logins. A security mechanism enforces a 60-second account lockout after five consecutive incorrect password attempts to mitigate brute-force attacks. Additionally, idle connections are terminated automatically after 5 minutes of inactivity.

4.   Logging: Critical security events (registrations, logins, lockouts, and timeouts) are securely tracked in security_log.txt without exposing sensitive user credentials.

Sample Screenshots

<img width="970" height="727" alt="successful_authentication" src="https://github.com/user-attachments/assets/1be944e4-6057-454f-b244-933387ae99db" />
Authentication & Chat Interface
<img width="1853" height="888" alt="successful_login_wireshark" src="https://github.com/user-attachments/assets/ebc9313b-05d6-4e89-b00b-14dc3f16a9ac" />
Security Features Triggered (Duplicate/Lockout)
<img width="470" height="567" alt="duplicate_login_prevention" src="https://github.com/user-attachments/assets/6032c690-206f-4422-9212-2e4879b0749d" />
Wireshark Verification (TCP Handshake & Login)


## Author
**Gouriniban Borphukan** | Roll No. CSB24032
B.Tech Computer Science & Engineering — Tezpur University
ISEA Phase 3 Internship
