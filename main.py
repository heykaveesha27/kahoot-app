import customtkinter
from server_window import ServerWindow
import socket
import threading
import queue
import time

customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("dark-blue")

HEADER = 64
PORT = 5050
DISCOVERY_PORT = 5051
SERVER_PASSWORD = "1234"
SERVER = "0.0.0.0"
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISONNECTED_MESSAGE = "DISCONNECTED"


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR, 1)
server.bind(ADDR)

msg_queue = queue.Queue()
clients=[]
client_names = {}
scores = {}
current_correct = None
clients_lock = threading.Lock()
session_window = None
session_active = False

def set_current_correct(val):
    global current_correct
    with clients_lock:
        current_correct = val

def recv_exact(sock, nbytes):
    data = b""
    while len(data) < nbytes:
        try:
            chunk = sock.recv(nbytes - len(data))
        except socket.timeout:
            return b""
        if not chunk:
            return None
        data += chunk
    return data

def send_framed(sock, text):
    payload = text.encode(FORMAT)
    send_length = str(len(payload)).encode(FORMAT)
    send_length += b' ' * (HEADER - len(send_length))
    sock.sendall(send_length)
    sock.sendall(payload)

def authenticate_client(conn, addr):
    """Expect PASS:<password> as the first message."""
    try:
        conn.settimeout(5)
        raw_length = recv_exact(conn, HEADER)
        if raw_length is None or raw_length == b"":
            return False
        msg_length_txt = raw_length.decode(FORMAT).strip()
        if not msg_length_txt.isdigit():
            return False
        msg_length = int(msg_length_txt)
        msg_raw = recv_exact(conn, msg_length)
        if msg_raw is None or msg_raw == b"":
            return False
        msg = msg_raw.decode(FORMAT)
        if msg.startswith("PASS:") and msg.split("PASS:", 1)[1] == SERVER_PASSWORD:
            send_framed(conn, "AUTH_OK")
            return True
        send_framed(conn, "AUTH_FAIL")
        return False
    except Exception:
        try:
            send_framed(conn, "AUTH_FAIL")
        except Exception:
            pass
        return False

def discovery_server():
    """UDP discovery responder for LAN auto-join."""
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind(("", DISCOVERY_PORT))
    while True:
        try:
            data, addr = udp.recvfrom(1024)
            if data.decode(FORMAT).strip() == "DISCOVER":
                reply = f"SERVER:{SERVER}:{PORT}"
                udp.sendto(reply.encode(FORMAT), addr)
        except Exception:
            continue

def handle_client(conn, addr):
    global session_active
    print(clients)
    print(f"[NEW CONNECTION] {addr} connected.")
    connected=True
    # Use a short timeout so the loop can notice session start and handoff
    try:
        conn.settimeout(0.5)
    except Exception:
        pass
    handoff_to_session = False
    while connected:
        if session_active:
            handoff_to_session = True
            break
        try:
            raw_length = recv_exact(conn, HEADER)
            if raw_length is None:
                break
            if raw_length == b"":
                continue

            msg_length_txt = raw_length.decode(FORMAT).strip()
            if not msg_length_txt:
                continue
            if not msg_length_txt.isdigit():
                print(f"[WARN] Invalid header from {addr}: {msg_length_txt!r}")
                continue

            msg_length = int(msg_length_txt)
            msg_raw = recv_exact(conn, msg_length)
            if msg_raw is None:
                break
            if msg_raw == b"":
                continue

            msg = msg_raw.decode(FORMAT)
            if msg==DISONNECTED_MESSAGE:
                connected = False
            else:
                print(f"[{addr}] {msg}")     
                line = f"[{addr}] {msg}\n"
                msg_queue.put(line)

                if " has joined the server" in msg:
                    name = msg.split(" has joined the server")[0]
                    with clients_lock:
                        client_names[conn] = name
                        if name not in scores:
                            scores[name]=0
        except Exception:
            break
    if handoff_to_session:
        return
    with clients_lock:
        if conn in clients:
            clients.remove(conn)
    conn.close()
    
def pump_messages():
    while not msg_queue.empty():
        line = msg_queue.get()
        participants_textbox.insert("end",line)
        participants_textbox.see("end")
    root.after(100, pump_messages)

def start():
    global session_window, session_active
    server.listen()
    print(f"[LISTENING] Server is listening on {server}")
    while True:
        conn,addr=server.accept()
        if not authenticate_client(conn, addr):
            print(f"[AUTH] Rejected connection from {addr}")
            try:
                conn.close()
            except Exception:
                pass
            continue

        with clients_lock:
            clients.append(conn)
            active_window = session_window
            active_session = session_active
        if active_window is not None:
            try:
                active_window.after(0, active_window.add_clients,conn,addr)
            except Exception as e:
                print(f"[WARNING] Failed to handoff client to session window: {e}")
        if not active_session:
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.active_count()-1}")

print("[STARTING] server is starting...")

# Start server in background thread
import time
discovery_thread = threading.Thread(target=discovery_server, daemon=True)
discovery_thread.start()
server_thread = threading.Thread(target=start, daemon=True)
server_thread.start()
time.sleep(1)  # Give server time to start listening

root = customtkinter.CTk()
root.geometry("320x480")
root.title("Quiz App")

frame = customtkinter.CTkFrame(master=root)
frame.pack(fill="both", expand=True)

label=customtkinter.CTkLabel(master=frame, text="Start New Session", font=("Roboto", 24))
label.pack(pady=12,padx=10)

sessionname_label=customtkinter.CTkLabel(master=frame,text="Session Name")
sessionname_label.pack(pady=(8,2),padx=10,anchor="w")

session_name_var = customtkinter.StringVar()

entry1=customtkinter.CTkEntry(master=frame,placeholder_text="Session Name",textvariable=session_name_var)
entry1.pack(pady=(0,10),padx=10,fill="x")



def open_server():
    global session_window, session_active
    session_name=session_name_var.get()
    print(session_name)
    session_active = True
    with clients_lock:
        # Clear timeouts for active session listeners
        for c in list(clients):
            try:
                c.settimeout(None)
            except Exception:
                pass
    root.withdraw()
    session_window = ServerWindow(root,session_name,clients=clients,initial_scores=scores)

button=customtkinter.CTkButton(master=frame,text="Start Session",command=open_server,height=32,corner_radius=8)
button.pack(pady=10,padx=10)

participants_label=customtkinter.CTkLabel(master=frame,text="participants")
participants_label.pack(pady=(8,2),padx=10,anchor="w")

participants_textbox=customtkinter.CTkTextbox(master=frame,height=200)
participants_textbox.pack(pady=(0,10),padx=10,fill="both",expand=True)

pump_messages()

root.mainloop()
