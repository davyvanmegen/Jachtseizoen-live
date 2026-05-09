import socket

from daphne.management.commands.runserver import Command as DaphneRunserverCommand


def get_lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        pass

    try:
        host = socket.gethostname()
        for address in socket.gethostbyname_ex(host)[2]:
            if not address.startswith("127."):
                return address
    except OSError:
        return None
    return None


class Command(DaphneRunserverCommand):
    default_addr = "0.0.0.0"

    def inner_run(self, *args, **options):
        lan_ip = get_lan_ip()
        port = self.port
        if lan_ip:
            self.stdout.write(self.style.SUCCESS(f"Netwerkadres: http://{lan_ip}:{port}/"))
            self.stdout.write("Open dit adres op je telefoon zolang die op hetzelfde netwerk zit.\n")
        else:
            self.stdout.write(self.style.WARNING("Geen LAN IP-adres gevonden. Probeer ipconfig en gebruik je IPv4-adres.\n"))
        super().inner_run(*args, **options)
