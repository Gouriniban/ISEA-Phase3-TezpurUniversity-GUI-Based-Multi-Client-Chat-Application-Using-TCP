
# Optimized & Scalable GUI-Based Multi-Client Chat Application (TCP)

## Objective
To enhance the existing GUI-based multi-client chat application by improving scalability, reliability, maintainability, and overall software quality. This project builds upon the secure TCP chat architecture to support concurrent usage, handle network interruptions gracefully, and externalize parameters into a configuration file.

## Software Requirements
* **Language:** Python 3.x
* **Libraries:** `tkinter` (GUI), `socket`, `threading`, `hashlib`, `psutil` (for resource monitoring), `matplotlib` (for performance graphs)
* **Environment:** Mininet (Network Emulator)
* **Analysis Tool:** Wireshark (for packet capturing)
* **Operating System:** Ubuntu/Linux recommended

## Network Topology
The application is designed and tested within a Mininet virtual network using a single-switch topology with 11 nodes to prove scalability:
* **h1:** Chat Server
* **h2 to h11:** 10 Concurrent Clients

## Execution Steps

1. **Start the Mininet Network:**
   Open a terminal and launch the 11-node topology:

   sudo mn --topo single,11
   Configure the Application:
Modify parameters in config.json (such as server_ip, port, and max_clients) before starting.

Start the Chat Server:Inside the Mininet CLI, run the server on host 1 (h1):

mininet> h1 python3 server.py &

Launch the Clients:
Open terminal windows for the client hosts (e.g., testing with 10 clients):

mininet> xterm h2 h3 h4 h5 h6 h7 h8 h9 h10 h11

Connect to the Chat:In each xterm window, execute the client GUI script:Bashpython3 client_gui.py
(Note: The client will automatically pull the Server IP and Port from config.json.) 

Graceful Shutdown & Performance Metrics:

To stop the server, bring it to the foreground and press Ctrl + C. It will intercept the signal, close sockets safely, and generate performance graphs (resource_usage.png and throughput.png) in the /graphs directory.  Brief Description of the ImplementationThis project optimizes a secure TCP chat application to be highly reliable and scalable.

Configuration Management: Hardcoded values were completely removed. Network parameters, security thresholds, and timeouts are managed entirely through config.json. 

Reliability (Auto-Reconnect & Graceful Shutdown): The client features automatic background reconnection to recover from dropped connections automatically. 
The server traps termination signals (SIGINT) to broadcast shutdown warnings, safely terminate active sockets, and prevent network state corruption.

Scalability: Thread management and dictionary tracking were optimized to handle 10 concurrent clients without crashing.

Performance Evaluation: A background daemon thread utilizing psutil monitors server CPU usage, memory consumption, average delay, and message throughput, exporting the results to performance_results.csv and generating visual plots.

Sample Screenshots

<img width="970" height="727" alt="Screenshot From 2026-07-23 02-54-02" src="https://github.com/user-attachments/assets/df718450-680c-4e73-b94c-5273c7c2e8f0" />

Scalability

<img width="970" height="727" alt="reconnection_success" src="https://github.com/user-attachments/assets/a7e55794-dc02-40b0-9a2f-ec35e51abc03" />

Reliability

<img width="1050" height="596" alt="Screenshot From 2026-07-23 04-08-21" src="https://github.com/user-attachments/assets/5a8e4aea-0f7a-4729-960a-173956e08211" />

Performance Evaluation

<img width="1920" height="920" alt="wireshark_normal_operation" src="https://github.com/user-attachments/assets/57896c04-2fee-49bd-80e3-69e23e9d9669" />


GraphsWireshark Verification (Normal Traffic)
