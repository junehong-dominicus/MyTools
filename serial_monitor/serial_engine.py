import codecs
import serial
import threading
import time
import os
from datetime import datetime

class SerialEngine:
    def __init__(self, port, baudrate, on_data_received, on_error=None):
        self.port = port
        self.baudrate = baudrate
        self.on_data_received = on_data_received
        self.on_error = on_error
        self.ser = None
        self.running = False
        self.thread = None
        self.log_file = None
        self.log_filename = None
        # Guards log_file: stop() may close it while a slow reader thread that
        # outlived join(timeout) is still writing.
        self._log_lock = threading.Lock()
        self._stopped = False
        
        # Ensure logs directory exists
        self.logs_dir = "logs"
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
        
        self.max_log_size = 10 * 1024 * 1024 # 10 MB
        self.max_logs_to_keep = 5
        self.current_log_size = 0
        self._cleanup_old_logs()

    def _create_log_file(self):
        if self.log_file:
            self.log_file.close()
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_port = self.port.replace("/", "_").replace("\\", "_").replace(":", "")
        log_filename = os.path.join(self.logs_dir, f"log_{safe_port}_{timestamp}.txt")
        self.log_file = open(log_filename, "a", encoding="utf-8")
        self.log_filename = os.path.abspath(log_filename)
        self.current_log_size = 0
        self._cleanup_old_logs()

    def get_log_path(self):
        return self.log_filename

    def start(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.running = True
            self._stopped = False

            with self._log_lock:
                self._create_log_file()
            
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            return True, "Connected"
        except Exception as e:
            self.running = False
            # Thread.start() can fail before the thread has an identity; joining
            # an unstarted thread raises and would prevent resource cleanup.
            if self.thread is not None and self.thread.ident is None:
                self.thread = None
            self.stop()
            self.log_filename = None
            return False, str(e)

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass
            self.ser = None
            
        with self._log_lock:
            if self.log_file:
                try:
                    self.log_file.flush()
                    self.log_file.close()
                except:
                    pass
                self.log_file = None
            self._stopped = True

        return True, "Disconnected"

    def send(self, data):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(data.encode('utf-8'))
                return True
            except Exception as e:
                print(f"Send error: {e}")
        return False

    def _cleanup_old_logs(self):
        try:
            safe_port = self.port.replace("/", "_").replace("\\", "_").replace(":", "")
            prefix = f"log_{safe_port}_"
            files = [f for f in os.listdir(self.logs_dir) if f.startswith(prefix) and f.endswith(".txt")]
            files.sort(key=lambda x: os.path.getmtime(os.path.join(self.logs_dir, x)))
            
            while len(files) > self.max_logs_to_keep:
                file_to_del = files.pop(0)
                os.remove(os.path.join(self.logs_dir, file_to_del))
        except Exception as e:
            print(f"Cleanup error: {e}")

    def _run(self):
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while self.running:
            if self.ser and self.ser.is_open:
                try:
                    if self.ser.in_waiting > 0:
                        data = self.ser.read(self.ser.in_waiting)
                        text = decoder.decode(data)
                        
                        # Callback to UI (skipped once stop() has completed)
                        if self._write_log(text, len(data)) and self.on_data_received:
                            self.on_data_received(text)
                except Exception as e:
                    print(f"Read error on {self.port}: {e}")
                    self.running = False
                    if self.on_error:
                        self.on_error(str(e))
            time.sleep(0.01)

        tail = decoder.decode(b"", final=True)
        # If stop() already gave up waiting and finished, the pane shows
        # disconnected; drop the tail rather than append to a closed session.
        if tail and self._write_log(tail, 0) and self.on_data_received:
            self.on_data_received(tail)

    def _write_log(self, text, nbytes):
        """Append to the log; returns False once stop() has completed."""
        with self._log_lock:
            if self._stopped:
                return False
            if self.log_file:
                self.log_file.write(text)
                self.log_file.flush()
                self.current_log_size += nbytes
                if self.current_log_size >= self.max_log_size:
                    self._create_log_file()
            return True
