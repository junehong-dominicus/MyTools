import socket
import psutil
import ipaddress
import threading
from threading import Lock
from scapy.all import ARP, Ether, srp
from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
import requests
import time

class EmbeddedSystemScanner:
    def __init__(self):
        self.devices = {}
        self._devices_lock = Lock()
        self.scanning = False
        self._stop = False
        self.was_stopped = False
        self.manufacturer_map = {
            # Epic Safety Inc. assigned OUIs
            "f0:24:f9": "Epic Safety Inc. (Embedded System)",
            "44:1d:64": "Epic Safety Inc.",
            # Espressif OUIs used on Embedded System / Embedded System modules
            "e8:b0:c5": "Espressif (Embedded System Node)",   # ESP32-WROVER-E
            "4c:75:25": "Espressif (Embedded System Node)",
            "30:ae:a4": "Espressif (Embedded System Node)",
            "c4:d8:d5": "Espressif (Embedded System Node)",
            "24:0a:c4": "Espressif (Embedded System Node)",
            "a4:e5:7c": "Espressif (Embedded System Node)",
            "3c:71:bf": "Espressif (Embedded System Node)",
            "d8:bf:c0": "Espressif (Embedded System Node)",
            "84:f7:03": "Espressif (Embedded System Node)",
            "78:1c:3c": "Espressif",                # ESP-AT module (Embedded System Ethernet MAC)
        }

    # Adapter-name hints used to tell wireless interfaces from wired ones.
    WIFI_HINTS = ("wi-fi", "wifi", "wireless", "wlan")
    # Virtual / non-physical adapters that are never real field interfaces.
    # "local area connection*" (with the asterisk) is the Wi-Fi Direct virtual
    # adapter Windows creates — distinct from a plain "Local Area Connection" NIC.
    IGNORE_HINTS = ("vethernet", "default switch", "loopback", "bluetooth",
                    "virtualbox", "vmware", "hyper-v", "local area connection*",
                    "tailscale", "tap-", "tun", "vpn", "wsl")

    def iface_category(self, name):
        """Classify a psutil interface name.

        Returns "Wi-Fi", "Ethernet", or None for virtual/irrelevant adapters
        that should never be scanned.
        """
        n = name.lower()
        if any(hint in n for hint in self.IGNORE_HINTS):
            return None
        if any(hint in n for hint in self.WIFI_HINTS):
            return "Wi-Fi"
        return "Ethernet"

    def _categories_for_selection(self, selection):
        """Map a dropdown label to the set of categories to scan.

        Returns None to mean "no filter" (scan every detected interface).
        """
        mapping = {
            "Ethernet": {"Ethernet"},
            "Wi-Fi": {"Wi-Fi"},
            "Ethernet & Wi-Fi": {"Ethernet", "Wi-Fi"},
        }
        return mapping.get(selection)

    def stop(self):
        """Request the in-progress scan to abort.

        full_scan() checks this flag between stages (ARP join, mDNS dwell, and
        before each HTTP probe) and returns whatever has been found so far.
        Blocking calls already in flight (scapy srp timeout, an open requests
        GET) are bounded by their own timeouts, so the abort is not instant but
        skips all remaining work.
        """
        self._stop = True

    def get_local_subnets(self):
        subnets = []
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if (addr.family == socket.AF_INET
                        and not addr.address.startswith("127.")
                        and not addr.address.startswith("169.254.")):  # skip APIPA link-local
                    # Get netmask to calculate CIDR
                    netmask = addr.netmask
                    if netmask:
                        try:
                            network = ipaddress.IPv4Network(f"{addr.address}/{netmask}", strict=False)
                            subnets.append((interface, network))
                        except Exception as e:
                            print(f"Error calculating subnet for {interface}: {e}")
        return subnets

    def arp_scan(self, interface, subnet):
        print(f"Scanning {interface} on {subnet}...")
        try:
            # Scapy needs the interface name or object. We attempt to match psutil name to scapy iface.
            ans, unans = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=str(subnet)), 
                             iface=interface, 
                             timeout=3, 
                             verbose=False)
            
            for snd, rcv in ans:
                ip = rcv.psrc
                mac = rcv.hwsrc
                with self._devices_lock:
                    if ip not in self.devices:
                        self.devices[ip] = {
                            "ip": ip,
                            "mac": mac,
                            "name": "Unknown",
                            "manufacturer": self.lookup_manufacturer(mac),
                            "services": []
                        }
        except Exception as e:
            print(f"ARP Scan error on {interface}: {e}")

    def lookup_manufacturer(self, mac):
        oui = mac.lower()[:8]
        return self.manufacturer_map.get(oui, "Unknown")

    def mdns_scan(self):
        class MyListener(ServiceListener):
            def __init__(self, scanner):
                self.scanner = scanner

            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info:
                    for addr in info.addresses:
                        ip = socket.inet_ntoa(addr)
                        with self.scanner._devices_lock:
                            if ip not in self.scanner.devices:
                                self.scanner.devices[ip] = {
                                    "ip": ip,
                                    "mac": "Unknown",
                                    "name": name.split(".")[0],
                                    "manufacturer": "Unknown",
                                    "services": []
                                }
                            self.scanner.devices[ip]["name"] = name.split(".")[0]
                            if "Embedded System" in name.lower():
                                self.scanner.devices[ip]["manufacturer"] = "Epic Safety Inc."

        zeroconf = Zeroconf()
        browser = ServiceBrowser(zeroconf, "_http._tcp.local.", MyListener(self))
        # Dwell in short slices so a stop request cuts the wait short.
        elapsed = 0.0
        while elapsed < 5.0 and not self._stop:
            time.sleep(0.2)
            elapsed += 0.2
        zeroconf.close()

    def _get_with_retry(self, url, timeout, attempts=3, backoff=0.4):
        """GET with retry on connection errors.

        Embedded System firmware (Embedded System_web_server.c) issues a delayed AT+CIPCLOSE on the
        link ID it just answered on. If a new connection arrives inside that
        ~160 ms window, ESP-AT reassigns the freed link ID and the stale
        CIPCLOSE kills the new connection before it is answered
        (RemoteDisconnected). Backing off briefly and retrying rides out the
        window.
        """
        for attempt in range(attempts):
            if self._stop:
                return None
            try:
                return requests.get(url, timeout=timeout)
            except requests.exceptions.ConnectionError:
                if attempt == attempts - 1:
                    raise
                # Interruptible backoff so a stop request aborts retries promptly
                # instead of riding out the full backoff + remaining attempts.
                slept = 0.0
                while slept < backoff and not self._stop:
                    time.sleep(0.05)
                    slept += 0.05
        return None

    def probe_services(self, ip, port=8000):
        if self._stop:
            return
        # ── Probe Embedded System (ESP32 httpd, responds quickly) ──────────────────────
        try:
            response = self._get_with_retry(f"http://{ip}:{port}/api/system/info", timeout=3)
            if response is not None and response.status_code == 200:
                data = response.json()
                # Primary check: explicit "device" field added in firmware v1.0+
                # Fallback: look for Embedded System-specific fields ("serial", "mac_eth", "free_heap")
                is_embedded_system = (
                    data.get("device", "").lower() == "Embedded System"
                    or "Embedded System" in data.get("version", "").lower()
                    or ("serial" in data and "mac_eth" in data)
                )
                if is_embedded_system:
                    with self._devices_lock:
                        if "Configuration WebUI" not in self.devices[ip]["services"]:
                            self.devices[ip]["services"].append("Configuration WebUI")
                        self.devices[ip]["name"]         = "Embedded System"
                        self.devices[ip]["manufacturer"] = data.get("manufacturer", "Epic Safety Inc.")
                        # Enrich with version and serial when available
                        if "version" in data:
                            self.devices[ip]["version"] = data["version"]
                        if "serial" in data:
                            self.devices[ip]["serial"] = data["serial"]
                    return   # identified — skip Embedded System probe for this IP
        except Exception:
            pass

        if self._stop:
            return

        # ── Probe Embedded System (ESP-AT TCP stack — use generous timeout) ────────────
        try:
            response = self._get_with_retry(f"http://{ip}:{port}/api/info", timeout=5)
            if response is not None and response.status_code == 200:
                data = response.json()
                # "slot" field is unique to Embedded System's OTA metadata response
                if "slot" in data or "build" in data:
                    with self._devices_lock:
                        if "Configuration WebUI" not in self.devices[ip]["services"]:
                            self.devices[ip]["services"].append("Configuration WebUI")
                        self.devices[ip]["name"]         = "Embedded System"
                        self.devices[ip]["manufacturer"] = "Epic Safety Inc."
                        if "build" in data:
                            self.devices[ip]["version"] = data["build"]
        except Exception:
            pass

    def full_scan(self, target_interface=None, callback=None):
        self.devices = {}
        self._stop = False
        self.was_stopped = False
        self.scanning = True
        try:
            subnets = self.get_local_subnets()

            # Drop virtual/irrelevant adapters (category None), then narrow to the
            # selected category (Ethernet / Wi-Fi). wanted is None only for the
            # CLI default, where we still skip the ignored adapters.
            wanted = self._categories_for_selection(target_interface)
            filtered = []
            for iface, subnet in subnets:
                cat = self.iface_category(iface)
                if cat is None:
                    continue
                if wanted is not None and cat not in wanted:
                    continue
                filtered.append((iface, subnet))
            subnets = filtered

            threads = []
            for interface, subnet in subnets:
                t = threading.Thread(target=self.arp_scan, args=(interface, subnet,))
                t.daemon = True
                t.start()
                threads.append(t)

            for t in threads:
                t.join()

            if self._stop:
                self.was_stopped = True
                return self.devices

            # mDNS scan in background
            mdns_thread = threading.Thread(target=self.mdns_scan)
            mdns_thread.daemon = True
            mdns_thread.start()

            # Probe HTTP for each found device (probe_services bails if stopped)
            probe_threads = []
            for ip in self.devices:
                if self._stop:
                    break
                t = threading.Thread(target=self.probe_services, args=(ip,))
                t.daemon = True
                t.start()
                probe_threads.append(t)

            for t in probe_threads:
                t.join()

            mdns_thread.join()

            if self._stop:
                self.was_stopped = True
        finally:
            self.scanning = False

        if callback:
            callback(self.devices)
        return self.devices

if __name__ == "__main__":
    scanner = EmbeddedSystemScanner()
    results = scanner.full_scan()
    for ip, data in results.items():
        print(f"Found: {data['name']} at {ip} ({data['manufacturer']})")
