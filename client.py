import customtkinter as ctk
import socket
import threading
import queue

HEADER = 64
PORT = 5050
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "DISCONNECTED"
SERVER=socket.gethostbyname(socket.gethostname())
ADDR=(SERVER,PORT)
DISCOVERY_PORT=5051
#SERVER = socket.gethostbyname(socket.gethostname())
#SERVER = "0.0.0.0"
ADDR = ('192.168.230.184', PORT)
#ADDR = (SERVER, PORT)
#DISCOVERY_PORT = 5051
FIXED_SERVER_IP="192.168.230.184"
score = 0
msg_queue = queue.Queue()
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
is_connected = False
latest_correct_answer = None
player_name = None

# Don't connect here - defer until needed
# client.connect(ADDR)

def discover_server(timeout=3.0):
    """Broadcast on LAN to find the server. Returns (ip, port) or None."""
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp.settimeout(timeout)
    try:
        udp.sendto(b"DISCOVER", ("255.255.255.255", DISCOVERY_PORT))
        data, _addr = udp.recvfrom(1024)
        msg = data.decode(FORMAT)
        if msg.startswith("SERVER:"):
            _, ip, port = msg.split(":", 2)
            return (ip, int(port))
    except Exception:
        return None
    finally:
        udp.close()
    return None

def connect_to_server(name, password):
    """Call this when you need to connect to the server"""
    global is_connected
    if is_connected:
        return True
    try:
        #found = discover_server()
        #if not found:
        #    print("[ERROR] Could not discover server on LAN.")
        #    return False
        #addr = found
        #client.connect(addr)
        # Send password first
        addr=(SERVER,PORT)
        client.connect(addr)
        send(f"PASS:{password}")
        raw_length = recv_exact(client, HEADER)
        if not raw_length:
            print("[ERROR] No auth response from server.")
            return False
        msg_length = int(raw_length.decode(FORMAT).strip())
        msg_raw = recv_exact(client, msg_length)
        if not msg_raw:
            print("[ERROR] No auth response from server.")
            return False
        auth_msg = msg_raw.decode(FORMAT)
        if auth_msg != "AUTH_OK":
            print("[ERROR] Password rejected by server.")
            try:
                client.close()
            except Exception:
                pass
            return False
        is_connected = True
        print(f"[{name}] Connected to server at {addr}")
        return True
    except ConnectionRefusedError:
        print(f"[ERROR] Could not connect to server at {ADDR}")
        print("Make sure the server is running first!")
        return False
    except OSError as e:
        print(f"[ERROR] Could not connect to server: {e}")
        return False

def send(msg):
    try:
        message = msg.encode(FORMAT)
        msg_length = len(message)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b' ' * (HEADER - len(send_length))
        client.sendall(send_length)
        client.sendall(message)
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")
        print("{name} joined the server")

def recv_exact(sock, nbytes):
    data = b""
    while len(data) < nbytes:
        chunk = sock.recv(nbytes - len(data))
        if not chunk:
            return None
        data += chunk
    return data

def update_leaderboard(text):
    def _apply():
        leaderboard_textbox.configure(state="normal")
        leaderboard_textbox.delete("1.0","end")
        leaderboard_textbox.insert("end", text if text else "No players yet.\n")
        leaderboard_textbox.configure(state="disabled")
    root.after(0, _apply)

def recieve_question(callback):
    """Continuously listen for question and 4 answers from server"""
    print("[DEBUG] recieve thread started")
    try:
        while True:
            raw_length = recv_exact(client, HEADER)
            if not raw_length:
                print("[INFO] Server closed the connection.")
                break
            msg_length = int(raw_length.decode(FORMAT).strip())
            msg_raw = recv_exact(client, msg_length)
            if not msg_raw:
                print("[INFO] Server closed the connection.")
                break
            msg_type = msg_raw.decode(FORMAT)

            if msg_type =="LEADERBOARD":
                lb_len_raw = recv_exact(client, HEADER)
                if not lb_len_raw:
                    print("[INFO] Sever closed the connection.")
                    break
                lb_len = int(lb_len_raw.decode(FORMAT).strip())
                lb_raw = recv_exact(client, lb_len)
                if not lb_raw:
                    print("[INFO] Server closer the Connection")
                    break
                leaderboard_text=lb_raw.decode(FORMAT)
                update_leaderboard(leaderboard_text)
                continue
            
            if msg_type != "QUESTION":
                print(f"[WARN] Unknown message type: {msg_type!r}")
                continue

            q_len_raw = recv_exact(client,HEADER)
            if not q_len_raw:
                print("[INFO] Server closed the connection.")
                break

            q_len = int(q_len_raw.decode(FORMAT).strip())
            q_raw = recv_exact(client, q_len)
            if not q_raw:
                print("[INFO] Server closed the connection.")
                break

            question = q_raw.decode(FORMAT)

            answers = []
            for _ in range(4):
                ans_length_raw = recv_exact(client, HEADER)
                if not ans_length_raw:
                    print("[INFO] Server closed the connection.")
                    return
                ans_length = int(ans_length_raw.decode(FORMAT).strip())
                ans_raw = recv_exact(client, ans_length)
                if not ans_raw:
                    print("[INFO] Server closed the connection.")
                    return
                ans = ans_raw.decode(FORMAT)
                answers.append(ans)

            correct_length_raw = recv_exact(client, HEADER)
            if not correct_length_raw:
                print("[INFO] Server closed the connection.")
                break
            correct_length = int(correct_length_raw.decode(FORMAT).strip())
            correct_raw = recv_exact(client, correct_length)
            if not correct_raw:
                print("[INFO] Server closed the connection.")
                break
            correct_answer = correct_raw.decode(FORMAT)



            print(f"[RECIEVED] question={question}, answers={answers}, correct={correct_answer}")
            callback(question, answers,correct_answer)
    except ConnectionResetError:
        print("[INFO] Connection reset by server.")
    except OSError as e:
        if getattr(e, "winerror", None) == 10054:
            print("[INFO] Connection closed by server (WinError 10054).")
        else:
            print(f"[ERROR] Socket error while receiving: {e}")
    except Exception as e:
        print(f"[ERROR] Failed to recieve: {e}")

def reset_answer_checkboxes():
    for cb in (cb1,cb2,cb3,cb4):
        cb.deselect()
        cb.configure( 
            border_color=("#3E454A","#949A9f"),
            fg_color = ("#3B8ED0","#1F6AA5"),
            checkmark_color=("#DCE4EE","gray90"),
        )

def highlight_correct_checkbox(correct_answer):
    reset_answer_checkboxes()
    mapping = {"1":cb1, "2":cb2, "3":cb3, "4":cb4}
    correct_cb = mapping.get(correct_answer)
    if correct_cb:
        correct_cb.select()
        correct_cb.configure(
            border_color=("#16A34A","#16A34A"),
            fg_color = ("#22C55E","#16A34A"),
            checkmark_color=("#FFFFFF","#FFFFFF"),
        )

def highlight_answer_result(user_answer, correct_answer):
    reset_answer_checkboxes()
    mapping = {"1":cb1,"2":cb2,"3":cb3,"4":cb4}
    user_cb = mapping.get(user_answer)
    correct_cb=mapping.get(correct_answer)
    if user_cb:
        user_cb.select()
        if user_answer==correct_answer:
            user_cb.configure(
            border_color=("#16A34A","#16A34A"),
            fg_color = ("#22C55E","#16A34A"),
            checkmark_color=("#FFFFFF","#FFFFFF"),
        )
        else:
            user_cb.configure(
                border_color = ("#DC2626","#DC2626"),
                fg_color=("#EF4444","#DC2626"),
                checkmark_color = ("#FFFFFF","#FFFFFF"),
            )
    if correct_cb and user_answer != correct_answer:
        correct_cb.select()
        correct_cb.configure(
            border_color=("#16A34A", "#16A34A"),
            fg_color = ("#22C55E", "#16A34A"),
            checkmark_color = ("#FFFFFF","#FFFFFF"),
        )
        
def to_leaderboard(name,score):
    """send player name and score to server"""
    try:
        message = f"{name}:{score}".encode(FORMAT)
        msg_length = len(message)
        send_length = str(msg_length).encode(FORMAT)
        send_length +=b' ' * (HEADER-len(send_length))
        client.sendall(send_length)
        client.sendall(message)
    except Exception as e:
        print(f"[ERROR] Failed to send leaderboard data : {e}")

def send_answer():
    global score
    correct_ans = None
    if cb1.get():
        correct_ans="1"
    elif cb2.get():
        correct_ans="2"
    elif cb3.get():
        correct_ans="3"
    elif cb4.get():
        correct_ans="4"

    if correct_ans is None:
        return

    try:
        message = correct_ans.encode(FORMAT)
        msg_length = len(message)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b' ' * (HEADER - len(send_length))
        client.sendall(send_length)
        client.sendall(message)
        if latest_correct_answer:
            highlight_answer_result(correct_ans,latest_correct_answer)
            if correct_ans==latest_correct_answer:
                score += 1
                to_leaderboard(player_name, score)

    except Exception as e:
        print(f"The answer wasn't sent: {e}")

    for cb in (cb1,cb2,cb3,cb4):
        cb.configure(state = "disabled")

    button3.configure(state = "disabled")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root=ctk.CTk()
root.geometry("360x540")

def leave_session():
    root.title("Quiz App")
    show_join_dialog(on_join)

# ---dialog --


def show_join_dialog(on_join):
    dialog = ctk.CTkToplevel(root)
    dialog.title("Join Session")
    dialog.geometry("300x240")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()

    container = ctk.CTkFrame(dialog)
    container.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(container, text="Enter your name", font=("Roboto", 16)).pack(anchor="w")

    name_entry = ctk.CTkEntry(container, placeholder_text="Name")
    name_entry.pack(fill="x", pady=(0, 0))
    name_entry.focus_set()

    error_label = ctk.CTkLabel(container, text="", text_color="red")
    error_label.pack(anchor="w")

    ctk.CTkLabel(container, text="Session Password", font=("Roboto", 14)).pack(anchor="w", pady=(8, 0))
    pass_entry = ctk.CTkEntry(container, placeholder_text="Password", show="*")
    pass_entry.pack(fill="x", pady=(0, 0))

    def submit():
        name = name_entry.get().strip()
        if not name:
            error_label.configure(text="Name is required.")
            return
        password = pass_entry.get().strip()
        if not password:
            error_label.configure(text="Password is required.")
            return
        if not connect_to_server(name, password):
            error_label.configure(text="Cannot connect to server. Check password or server.")
            return
        dialog.destroy()
        send(f"{name} has joined the server")
        on_join(name)
        recieve_thread = threading.Thread(target=recieve_question, args=(update_question,),daemon=True)
        recieve_thread.start()



    join_btn = ctk.CTkButton(container, text="Join Session" ,command=submit)
    join_btn.pack(pady=(8, 0),side="left")

    def close_all():
        dialog.destroy()
        root.destroy()
       


    close_btn = ctk.CTkButton(container,text="Cancel",command=close_all)
    close_btn.pack(pady=(8,0),side="right")

    dialog.bind("<Return>", lambda _e: submit())



def on_join(name):
    global score, player_name
    print("Joined as:",name)
    score=0
    player_name = name
    
    root.title(f"{name}-Quiz App")

show_join_dialog(on_join)

tabs=ctk.CTkTabview(master=root)
tabs.pack(fill="both",expand=True,padx=0,pady=0)

tab_Session=tabs.add("Session")
tab_Leaderbord=tabs.add("Leaderboard")

frame=ctk.CTkFrame(master=tab_Session)
frame.pack(fill="both",expand=True)

top_row = ctk.CTkFrame(master=frame, fg_color="transparent")
top_row.pack(pady=(4, 10), padx=0, fill="x")

label1=ctk.CTkLabel(master=top_row,text=f"New Session",font=("Roboto",24))
label1.pack(pady=12,padx=10,side="left")

leaderboardbtn=ctk.CTkButton(master=top_row,text="Leave Session",command=leave_session)
leaderboardbtn.pack(pady=12,padx=10,side="right")

label2=ctk.CTkLabel(master=frame,text="Questions")
label2.pack(pady=(12,2),padx=10,anchor="w")

entry1=ctk.CTkEntry(master=frame,placeholder_text="Question",height=32)
entry1.pack(pady=(0,10),padx=10,fill="x")
entry1.configure(state="disabled")

def update_question(question_text, answers, correct_answer):
    """callback to update the question entry"""
    global latest_correct_answer
    latest_correct_answer = correct_answer
    reset_answer_checkboxes()

    entry1.configure(state="normal")
    entry1.delete(0, "end")
    entry1.insert(0, question_text)
    entry1.configure(state="disabled")

    for cb in (cb1,cb2,cb3,cb4):
        cb.configure(state = "normal")

    button3.configure(state = "normal")

    try:
        answer1.configure(state="normal");answer1.delete(0,"end");answer1.insert(0,answers[0]);answer1.configure(state="disabled")
        answer2.configure(state="normal");answer2.delete(0,"end");answer2.insert(0,answers[1]);answer2.configure(state="disabled")
        answer3.configure(state="normal");answer3.delete(0,"end");answer3.insert(0,answers[2]);answer3.configure(state="disabled")
        answer4.configure(state="normal");answer4.delete(0,"end");answer4.insert(0,answers[3]);answer4.configure(state="disabled")
    except Exception as e:
        print(f"[WARN] failed to update answers UI: {e}")

label3=ctk.CTkLabel(master=frame,text="Answers")
label3.pack(pady=0,padx=10,anchor="w")

answer1=ctk.CTkEntry(master=frame,placeholder_text="Answer 1",height=32)
answer1.pack(pady=(0,10),padx=10,fill="x")
answer1.configure(state="disabled")

answer2=ctk.CTkEntry(master=frame,placeholder_text="Answer 2",height=32)
answer2.pack(pady=(0,10),padx=10,fill="x")
answer2.configure(state="disabled")

answer3=ctk.CTkEntry(master=frame,placeholder_text="Answer 3",height=32)
answer3.pack(pady=(0,10),padx=10,fill="x")
answer3.configure(state="disabled")

answer4=ctk.CTkEntry(master=frame,placeholder_text="Answer 4",height=32)
answer4.pack(pady=(0,10),padx=10,fill="x")
answer4.configure(state="disabled")

checks_row = ctk.CTkFrame(master=frame, fg_color="transparent")
checks_row.pack(pady=(4, 10), padx=0, anchor="w")

label4=ctk.CTkLabel(master=checks_row,text="Correct Answer")
label4.pack(side="left",padx=(10,20))

cb1 = ctk.CTkCheckBox(master=checks_row, text="1",  width=60, checkbox_width=24, checkbox_height=24)
cb1.pack(side="left", padx=(0, 3))

cb2 = ctk.CTkCheckBox(master=checks_row, text="2",  width=60, checkbox_width=24, checkbox_height=24)
cb2.pack(side="left", padx=(0, 3))

cb3 = ctk.CTkCheckBox(master=checks_row, text="3", width=60, checkbox_width=24, checkbox_height=24)
cb3.pack(side="left", padx=(0, 3))

cb4 = ctk.CTkCheckBox(master=checks_row, text="4",  width=60, checkbox_width=24, checkbox_height=24)
cb4.pack(side="left")

bottom_row= ctk.CTkFrame(master=frame, fg_color="transparent")
bottom_row.pack(pady=(10,0), padx=0, fill="x")

button3=ctk.CTkButton(master=bottom_row,text="Answer",height=32,command=send_answer)
button3.pack(pady=10,padx=10)

frame_leaderboard=ctk.CTkFrame(master=tab_Leaderbord)
frame_leaderboard.pack(fill="both",expand=True)


top_row_leaderboard = ctk.CTkFrame(master=frame_leaderboard, fg_color="transparent")
top_row_leaderboard.pack(pady=(4, 10), padx=0, fill="x")

label5=ctk.CTkLabel(master=top_row_leaderboard,text="Leaderboard",font=("Roboto",24))
label5.pack(pady=12,padx=10,side="left")

leaderboard_textbox = ctk.CTkTextbox(master=frame_leaderboard, height=300)
leaderboard_textbox.pack(pady=10, padx=10, fill="both", expand=True)
leaderboard_textbox.configure(state="disabled")

players=[
    {"name":"Alex Johnson", "score":12450},
    {"name":"priya k.","score":11980},
    {"name":"michael b.", "score":11200},
    {"name":"Samantha","score":9500},
    {"name":"Liyanage","score":9300}
]


root.mainloop()
