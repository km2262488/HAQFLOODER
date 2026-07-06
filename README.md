# HAQ Flooder

Ini adalah script Python untuk menjalankan serangan sederhana jenis **HTTP Flood** dan **UDP Flood** 

## Fitur

*   **Dua Jenis Serangan:**
    *   **HTTP Flood:** Mengirim permintaan HTTP (GET atau POST) ke server web.
    *   **UDP Flood:** Mengirimkan paket UDP acak ke target.
*   **Bekerja di Termux Tanpa Root:** Tidak memerlukan hak akses root.
*   **Threading:** Menggunakan multi-threading untuk mengirim banyak permintaan secara bersamaan.
*   **Payload HTTP Bervariasi:** Mendukung metode GET dan POST dengan header yang realistis dan payload POST acak.
*   **Payload UDP Acak:** Mengirimkan data UDP acak dengan ukuran bervariasi.
*   **User Agent Realistis:** Menggunakan daftar User Agent dari perangkat mobile.
*   **Logging:** Mencatat statistik serangan (permintaan terkirim, error) ke file `attack_log.txt`.
*   **Statistik Real-time:** Menampilkan statistik serangan secara langsung di konsol.
*   **Konfigurasi:** Dapat dikonfigurasi melalui argumen command-line.

---

## Persyaratan
*   Python 3 terinstal di Termux.
*   Pustaka `colorama` dan `threading` (sudah bawaan Python).

---

## Instalasi

1.  **BISMILLAH**
2.  **Update dan Upgrade Paket:**
    ```bash
    pkg update && pkg upgrade
    ```
3.  **Instal Python:**
    ```bash
    pkg install python
    ```
4.  **Instal Pustaka `colorama`:**
    ```bash
    pip install colorama
    ```
5.  **Unduh Script:**
   
```bash
git clone https://github.com/km2262488/HAQFLOODER.git
cd HAQFLOODER
python flood.py <TARGET_IP> <TARGET_PORT> <THREADS> <ATTACK_TYPE> [HTTP_METHOD]
python flood.py <IP> <PORT> <THREADS_PER_PORT> http normal <DURATION> GET
# Atau POST
python flood.py <IP> <PORT> <THREADS_PER_PORT> http normal <DURATION> POST
python flood.py 192.168.1.100 80 500 http normal 60 GET

slow mode
python flood.py <IP> <PORT> <THREADS_PER_PORT> http slow <DURATION>

slow POST mode
python flood.py <IP> <PORT> <THREADS_PER_PORT> http slow <DURATION> POST
