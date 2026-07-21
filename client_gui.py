#!/usr/bin/env python3
"""
Assignment 6 — GUI-Based Multi-Client Chat Application
client_gui.py — tkinter GUI client

Tasks covered:
  Task 1 : GUI Login Window
  Task 2 : Graphical Chat Interface
  Task 3 : Online User List
  Task 4 : Messaging Features (broadcast + private)
  Task 5 : Background Receiver Thread
  Task 6 : Tested in Mininet
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import socket
import threading
import sys
import time

SERVER_IP = sys.argv[1] if len(sys.argv) > 1 else '10.0.0.1'
PORT      = 5000

C = {
    'bg_dark':  '#1e2530',
    'bg_mid':   '#252d3a',
    'bg_light': '#2e3847',
    'entry_bg': '#1a2030',
    'accent':   '#4a9eff',
    'green':    '#2ecc71',
    'red':      '#e74c3c',
    'yellow':   '#f39c12',
    'purple':   '#a29bfe',
    'white':    '#e8eaf0',
    'grey':     '#8892a4',
}


class ChatClient:
    """Networking layer — kept fully independent of GUI code."""

    def __init__(self):
        self.sock      = None
        self.username  = None
        self.connected = False
        self._on_msg   = None
        self._on_disc  = None

    def connect(self, ip, port, username):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(8)
            self.sock.connect((ip, port))
            self.sock.settimeout(None)

            prompt = self.sock.recv(1024).decode().strip()
            if 'ENTER_USERNAME' not in prompt:
                return False, 'Unexpected server response'

            self.sock.sendall(username.encode())
            self.username  = username
            self.connected = True

            welcome = self.sock.recv(2048).decode()
            return True, welcome

        except socket.timeout:
            return False, f'Timed out — is server running on {ip}:{port}?'
        except ConnectionRefusedError:
            return False, f'Connection refused on {ip}:{port}'
        except Exception as e:
            return False, str(e)

    def send(self, text):
        if self.connected and self.sock:
            try:
                self.sock.sendall(text.encode())
                return True
            except Exception:
                self.connected = False
        return False

    def send_pm(self, target, text):
        return self.send(f'/msg {target} {text}')

    def disconnect(self):
        self.connected = False
        try:
            if self.sock:
                self.sock.sendall('/quit'.encode())
                time.sleep(0.1)
                self.sock.close()
        except Exception:
            pass

    def start_receiver(self, on_msg, on_disc):
        self._on_msg  = on_msg
        self._on_disc = on_disc
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()

    def _recv_loop(self):
        """Background thread — never blocks the GUI thread."""
        while self.connected:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                text = data.decode()
                if text.startswith('[PM from'):
                    tag = 'pm_in'
                elif text.startswith('[PM to'):
                    tag = 'pm_out'
                elif text.startswith('[SERVER]'):
                    tag = 'server'
                elif text.startswith('[') and ']' in text:
                    tag = 'other'
                else:
                    tag = 'server'
                if self._on_msg:
                    self._on_msg(text, tag)
            except Exception:
                break
        self.connected = False
        if self._on_disc:
            self._on_disc()


class LoginWindow:
    """Task 1 — GUI login window with validation."""

    def __init__(self, root, on_connect):
        self.root       = root
        self.on_connect = on_connect
        self.client     = ChatClient()

        root.title('TCP Chat — Login')
        root.configure(bg=C['bg_dark'])
        root.resizable(False, False)
        w, h = 420, 400
        x = (root.winfo_screenwidth()  - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f'{w}x{h}+{x}+{y}')

        self._build()

    def _build(self):
        r = self.root

        tk.Frame(r, bg=C['accent'], height=5).pack(fill='x')

        logo = tk.Frame(r, bg=C['bg_dark'], pady=22)
        logo.pack(fill='x')
        tk.Label(logo, text='💬',
                 font=('Segoe UI', 36),
                 bg=C['bg_dark'], fg=C['accent']).pack()
        tk.Label(logo, text='TCP Chat — Assignment 6',
                 font=('Segoe UI', 14, 'bold'),
                 bg=C['bg_dark'], fg=C['white']).pack()
        tk.Label(logo, text='GUI Client',
                 font=('Segoe UI', 9),
                 bg=C['bg_dark'], fg=C['grey']).pack()

        card = tk.Frame(r, bg=C['bg_mid'], padx=30, pady=20)
        card.pack(fill='x', padx=24)

        tk.Label(card, text='Server IP',
                 font=('Segoe UI', 9),
                 bg=C['bg_mid'], fg=C['grey'],
                 anchor='w').pack(fill='x')
        self.ip_var = tk.StringVar(value=SERVER_IP)
        tk.Entry(card, textvariable=self.ip_var,
                 font=('Segoe UI', 11),
                 bg=C['entry_bg'], fg=C['white'],
                 insertbackground=C['white'],
                 relief='flat', bd=6).pack(fill='x', pady=(2, 12))

        tk.Label(card, text='Username',
                 font=('Segoe UI', 9),
                 bg=C['bg_mid'], fg=C['grey'],
                 anchor='w').pack(fill='x')
        self.user_var = tk.StringVar()
        self.user_entry = tk.Entry(
            card, textvariable=self.user_var,
            font=('Segoe UI', 11),
            bg=C['entry_bg'], fg=C['white'],
            insertbackground=C['white'],
            relief='flat', bd=6)
        self.user_entry.pack(fill='x', pady=(2, 0))
        self.user_entry.bind('<Return>', lambda e: self._do_connect())
        self.user_entry.focus()

        self.status_var = tk.StringVar(value='Enter username and press Connect')
        self.status_lbl = tk.Label(r, textvariable=self.status_var,
                                   font=('Segoe UI', 9),
                                   bg=C['bg_dark'], fg=C['grey'],
                                   wraplength=370)
        self.status_lbl.pack(pady=12)

        self.btn = tk.Button(
            r, text='  Connect  ',
            font=('Segoe UI', 11, 'bold'),
            bg=C['accent'], fg=C['white'],
            activebackground='#3a8eef',
            activeforeground=C['white'],
            relief='flat', bd=0,
            pady=9, cursor='hand2',
            command=self._do_connect)
        self.btn.pack(fill='x', padx=24)

    def _status(self, msg, color=None):
        self.status_var.set(msg)
        self.status_lbl.configure(fg=color or C['grey'])

    def _do_connect(self):
        username = self.user_var.get().strip()
        ip       = self.ip_var.get().strip()

        if not username:
            self._status('⚠  Username cannot be empty.', C['red'])
            self.user_entry.focus()
            return
        if len(username) < 2:
            self._status('⚠  Username must be at least 2 characters.', C['red'])
            return
        if ' ' in username:
            self._status('⚠  Username cannot contain spaces.', C['red'])
            return
        if not ip:
            self._status('⚠  Server IP cannot be empty.', C['red'])
            return

        self._status('Connecting…', C['accent'])
        self.btn.configure(state='disabled', text='Connecting…')
        self.root.update()

        threading.Thread(
            target=self._connect_thread,
            args=(ip, username), daemon=True).start()

    def _connect_thread(self, ip, username):
        ok, msg = self.client.connect(ip, PORT, username)
        self.root.after(0, self._connect_result, ok, msg)

    def _connect_result(self, ok, msg):
        if ok:
            self._status('✓  Connected!', C['green'])
            self.root.after(300, lambda: self.on_connect(self.client, msg))
        else:
            self._status(f'✗  {msg}', C['red'])
            self.btn.configure(state='normal', text='  Connect  ')


class ChatWindow:
    """Tasks 2, 3, 4, 5 — Main chat interface."""

    def __init__(self, root, client, welcome):
        self.root   = root
        self.client = client

        root.title(f'TCP Chat — {client.username}')
        root.configure(bg=C['bg_dark'])
        w, h = 920, 640
        x = (root.winfo_screenwidth()  - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f'{w}x{h}+{x}+{y}')
        root.minsize(700, 480)
        root.protocol('WM_DELETE_WINDOW', self._close)

        self._build()
        self._tags()

        if welcome:
            for line in welcome.strip().split('\n'):
                if line.strip():
                    self._append(line, 'server')

        client.start_receiver(on_msg=self._on_msg, on_disc=self._on_disc)
        self.entry.focus()

    def _build(self):
        r = self.root

        hdr = tk.Frame(r, bg=C['bg_mid'], height=46)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        tk.Label(hdr, text='💬  TCP Chat',
                 font=('Segoe UI', 13, 'bold'),
                 bg=C['bg_mid'], fg=C['white']).pack(side='left', padx=12)

        self.conn_lbl = tk.Label(hdr, text='● Connected',
                 font=('Segoe UI', 9),
                 bg=C['bg_mid'], fg=C['green'])
        self.conn_lbl.pack(side='left')

        tk.Label(hdr, text=f'  {self.client.username}',
                 font=('Segoe UI', 9, 'bold'),
                 bg=C['bg_mid'], fg=C['accent']).pack(side='right', padx=12)

        body = tk.Frame(r, bg=C['bg_dark'])
        body.pack(fill='both', expand=True)

        left = tk.Frame(body, bg=C['bg_dark'])
        left.pack(side='left', fill='both', expand=True)

        self.area = scrolledtext.ScrolledText(
            left,
            font=('Consolas', 10),
            bg=C['bg_dark'], fg=C['white'],
            relief='flat', bd=0,
            state='disabled', wrap='word',
            padx=10, pady=8)
        self.area.pack(fill='both', expand=True, padx=(8, 0), pady=(8, 0))

        inp = tk.Frame(left, bg=C['bg_mid'], pady=8, padx=8)
        inp.pack(fill='x', pady=(4, 8), padx=8)

        pm_row = tk.Frame(inp, bg=C['bg_mid'])
        pm_row.pack(fill='x', pady=(0, 4))
        tk.Label(pm_row, text='Private to:',
                 font=('Segoe UI', 8),
                 bg=C['bg_mid'], fg=C['grey']).pack(side='left')
        self.pm_var = tk.StringVar()
        tk.Entry(pm_row, textvariable=self.pm_var,
                 font=('Segoe UI', 9),
                 bg=C['entry_bg'], fg=C['purple'],
                 insertbackground=C['purple'],
                 width=18, relief='flat', bd=4).pack(side='left', padx=(6, 0))
        tk.Label(pm_row, text='(empty = broadcast)',
                 font=('Segoe UI', 8),
                 bg=C['bg_mid'], fg=C['grey']).pack(side='left', padx=6)

        msg_row = tk.Frame(inp, bg=C['bg_mid'])
        msg_row.pack(fill='x')

        self.msg_var = tk.StringVar()
        self.entry = tk.Entry(msg_row, textvariable=self.msg_var,
                 font=('Segoe UI', 11),
                 bg=C['entry_bg'], fg=C['white'],
                 insertbackground=C['white'],
                 relief='flat', bd=6)
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', lambda e: self._send())

        tk.Button(msg_row, text='Send ➤',
                 font=('Segoe UI', 10, 'bold'),
                 bg=C['accent'], fg=C['white'],
                 activebackground='#3a8eef',
                 relief='flat', bd=0,
                 padx=14, pady=6, cursor='hand2',
                 command=self._send).pack(side='left', padx=(6, 4))

        tk.Button(msg_row, text='Disconnect',
                 font=('Segoe UI', 10),
                 bg=C['red'], fg=C['white'],
                 activebackground='#c0392b',
                 relief='flat', bd=0,
                 padx=10, pady=6, cursor='hand2',
                 command=self._close).pack(side='left')

        right = tk.Frame(body, bg=C['bg_mid'], width=185)
        right.pack(side='right', fill='y', padx=(0, 8), pady=8)
        right.pack_propagate(False)

        tk.Label(right, text='Online Users',
                 font=('Segoe UI', 10, 'bold'),
                 bg=C['bg_mid'], fg=C['white'],
                 pady=8).pack(fill='x')

        tk.Frame(right, bg=C['accent'], height=2).pack(fill='x', padx=6)

        self.ulist = tk.Listbox(right,
                 font=('Segoe UI', 10),
                 bg=C['bg_mid'], fg=C['green'],
                 selectbackground=C['bg_light'],
                 selectforeground=C['white'],
                 relief='flat', bd=0,
                 activestyle='none',
                 cursor='hand2')
        self.ulist.pack(fill='both', expand=True, padx=6, pady=6)
        self.ulist.bind('<<ListboxSelect>>', self._pick_user)

        tk.Label(right, text='↑ Click to PM',
                 font=('Segoe UI', 8),
                 bg=C['bg_mid'], fg=C['grey'],
                 pady=3).pack()

        cmd = tk.Frame(right, bg=C['bg_light'], pady=6, padx=8)
        cmd.pack(fill='x')
        tk.Label(cmd, text='Commands',
                 font=('Segoe UI', 8, 'bold'),
                 bg=C['bg_light'], fg=C['grey']).pack(anchor='w')
        for c in ['/list', '/stats', '/quit']:
            tk.Label(cmd, text=c,
                     font=('Consolas', 8),
                     bg=C['bg_light'], fg=C['accent']).pack(anchor='w')

        sb = tk.Frame(r, bg=C['bg_mid'], height=22)
        sb.pack(fill='x', side='bottom')
        sb.pack_propagate(False)
        self.sb_var = tk.StringVar(
            value=f'Connected to {SERVER_IP}:{PORT}  |  User: {self.client.username}')
        tk.Label(sb, textvariable=self.sb_var,
                 font=('Segoe UI', 8),
                 bg=C['bg_mid'], fg=C['grey']).pack(side='left', padx=8)

    def _tags(self):
        self.area.tag_configure('server',
            foreground=C['yellow'], font=('Consolas', 10, 'italic'))
        self.area.tag_configure('self',
            foreground=C['accent'], font=('Consolas', 10, 'bold'))
        self.area.tag_configure('other',
            foreground=C['white'], font=('Consolas', 10))
        self.area.tag_configure('pm_in',
            foreground=C['green'], font=('Consolas', 10, 'bold'))
        self.area.tag_configure('pm_out',
            foreground=C['purple'], font=('Consolas', 10, 'bold'))
        self.area.tag_configure('ts',
            foreground=C['grey'], font=('Consolas', 8))

    def _append(self, text, tag='other'):
        self.area.configure(state='normal')
        ts = time.strftime('%H:%M:%S')
        self.area.insert('end', f'[{ts}] ', 'ts')
        self.area.insert('end',
            text if text.endswith('\n') else text + '\n', tag)
        self.area.configure(state='disabled')
        self.area.see('end')

    def _on_msg(self, text, tag):
        """Called from receiver thread — schedule update on main thread."""
        self.root.after(0, self._show_msg, text.strip(), tag)

    def _show_msg(self, text, tag):
        if not text:
            return
        if 'has joined the chat' in text:
            parts = text.replace('[SERVER]', '').strip().split()
            if parts:
                self._add_user(parts[0])
        elif 'has left the chat' in text:
            parts = text.replace('[SERVER]', '').strip().split()
            if parts:
                self._rm_user(parts[0])
        self._append(text, tag)

    def _on_disc(self):
        self.root.after(0, self._disc_ui)

    def _disc_ui(self):
        self.conn_lbl.configure(text='● Disconnected', fg=C['red'])
        self.sb_var.set('Disconnected from server')
        self._append('[Connection closed by server]', 'server')

    def _add_user(self, name):
        existing = list(self.ulist.get(0, 'end'))
        disp = f'  {name}'
        if disp not in existing and name != self.client.username:
            self.ulist.insert('end', disp)

    def _rm_user(self, name):
        items = list(self.ulist.get(0, 'end'))
        for i, item in enumerate(items):
            if item.strip() == name:
                self.ulist.delete(i)
                break

    def _pick_user(self, _event):
        """Click a username in the list to auto-fill the PM target field."""
        sel = self.ulist.curselection()
        if sel:
            self.pm_var.set(self.ulist.get(sel[0]).strip())
            self.entry.focus()

    def _send(self):
        text   = self.msg_var.get().strip()
        target = self.pm_var.get().strip()
        if not text:
            return
        if not self.client.connected:
            messagebox.showwarning('Not Connected',
                'You are disconnected from the server.')
            return
        if target:
            self.client.send_pm(target, text)
            self._append(f'[PM → {target}] {text}', 'pm_out')
        else:
            self.client.send(text)
            self._append(f'[{self.client.username}] {text}', 'self')
        self.msg_var.set('')
        self.entry.focus()

    def _close(self):
        if self.client.connected:
            self.client.disconnect()
        self.root.destroy()


class App:
    def __init__(self):
        self.root = tk.Tk()
        LoginWindow(self.root, on_connect=self._open_chat)
        self.root.mainloop()

    def _open_chat(self, client, welcome):
        for w in self.root.winfo_children():
            w.destroy()
        ChatWindow(self.root, client, welcome)


if __name__ == '__main__':
    App()
