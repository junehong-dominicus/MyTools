import serial
import threading
import time
import os
from datetime import datetime

class SerialEngine:
    def __init__(self, port, baudrate, on_data_received):
        self.port = port
        self.baudrate = baudrate
        self.on_data_received = on_data_received
        self.ser = None
        self.running = False
        self.thread = None
        self.log_file = None
        self.log_filename = None
        
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
            
            self._create_log_file()
            
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            return True, "Connected"
        except Exception as e:
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
            
        if self.log_file:
            try:
                self.log_file.flush()
                self.log_file.close()
            except:
                pass
            self.log_file = None
            
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
        while self.running:
            if self.ser and self.ser.is_open:
                try:
                    if self.ser.in_waiting > 0:
                        data = self.ser.read(self.ser.in_waiting)
                        text = data.decode('utf-8', errors='replace')
                        
                        # Write to log file
                        if self.log_file:
                            self.log_file.write(text)
                            self.log_file.flush()
                            self.current_log_size += len(data)
                            
                            # Check rotation
                            if self.current_log_size >= self.max_log_size:
                                self._create_log_file()
                        
                        # Callback to UI
                        if self.on_data_received:
                            self.on_data_received(text)
                except Exception as e:
                    print(f"Read error on {self.port}: {e}")
                    self.running = False
            time.sleep(0.01)
