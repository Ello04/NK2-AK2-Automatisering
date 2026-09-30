import pwinput
import serial
from serial.tools import list_ports
import time


# Passordene brukes også til å skjule passord i konsollens svar.
password = ""
enable_password = ""


def read_output(timeout=30):
    """Les til en CLI-prompt eller et spørsmål, i maksimalt timeout sekunder."""
    output = ""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if ser.in_waiting:
            output += ser.read(ser.in_waiting).decode(errors="ignore")

            for line in output.splitlines():
                line = line.strip()
                if line.endswith(("#", ">")):
                    return output

            last_line = output.strip().splitlines()[-1].lower() if output.strip() else ""
            questions = ("password:", "[yes/no]", "[yes]", "[confirm]", "press return")
            if any(question in last_line for question in questions):
                return output

        time.sleep(0.1)

    return output


def print_output(output):
    """Skjul passord selv om enheten ekkoer kommandoen tilbake."""
    for secret in (password, enable_password):
        if secret:
            output = output.replace(secret, "[hidden]")
    print(output)


def required_input(question):
    value = input(question).strip()
    while not value:
        value = input("Please enter a value. " + question).strip()
    return value


# --------------------------------------------------
# Finn tilgjengelige COM-porter
# --------------------------------------------------

ports = list(list_ports.comports())

if not ports:
    raise SystemExit("No serial ports found.")

print("\nAvailable serial ports:")

for x, port in enumerate(ports, start=1):
    print(f"{x}: {port.device} - {port.description}")


# --------------------------------------------------
# Velg COM-port
# --------------------------------------------------

while True:
    try:
        choice = int(input("\nChoose a number: "))

        if 1 <= choice <= len(ports):
            break

        print("Invalid choice.")

    except ValueError:
        print("Please enter a number.")

selected = ports[choice - 1]
print(f"\nSelected: {selected.device}")


# --------------------------------------------------
# Koble til serial
# --------------------------------------------------

try:
    ser = serial.Serial(selected.device, baudrate=9600, timeout=2, write_timeout=5)
except serial.SerialException as error:
    raise SystemExit(f"Could not open serial port: {error}")

try:
    time.sleep(2)

    # --------------------------------------------------
    # Initialiser konsollen
    # --------------------------------------------------

    ser.write(b"\r\n")
    s = read_output()

    print("\nDevice output:")
    print_output(s)

    # --------------------------------------------------
    # Håndter Initial Configuration Dialog
    # --------------------------------------------------

    if "initial configuration" in s.lower():
        ser.write(b"no\r\n")
        s = read_output()
        print_output(s)

    if "terminate autoinstall" in s.lower():
        ser.write(b"yes\r\n")
        s = read_output()
        print_output(s)

    if "press return" in s.lower():
        ser.write(b"\r\n")
        s = read_output()
        print_output(s)

    if not any(line.strip().endswith(("#", ">")) for line in s.splitlines()):
        raise SystemExit("No CLI prompt found. Check console login and baud rate.")

    # --------------------------------------------------
    # Hent informasjon fra bruker
    # --------------------------------------------------

    print("\nDevice setup")

    while True:
        device_type = input("Device type (router/switch): ").strip().lower()
        if device_type in ["router", "switch"]:
            break
        print("Please enter 'router' or 'switch'.")

    hostname = required_input("Hostname: ")
    username = required_input("Username: ")

    while not password:
        password = pwinput.pwinput("Password: ")
        if not password:
            print("Password cannot be empty.")

    device_ip = required_input("Management IP: ")
    subnet_mask = input("Subnet mask [255.255.255.0]: ").strip() or "255.255.255.0"
    domain_name = input("Domain name [lab.local]: ").strip() or "lab.local"

    if device_type == "router":
        interface_name = required_input("Ethernet interface (example: GigabitEthernet0/0/0): ")
    else:
        interface_name = required_input("Switch port connected to PC (example: GigabitEthernet0/1): ")
        vlan_id = input("Management VLAN [1]: ").strip() or "1"
        gateway = input("Default gateway (Enter if PC is in the same subnet): ").strip()

    # --------------------------------------------------
    # Gå til privileged EXEC før konfigurasjon
    # --------------------------------------------------

    ser.write(b"enable\r\n")
    s = read_output()

    if "password:" in s.lower():
        enable_password = pwinput.pwinput("Existing enable password: ")
        ser.write((enable_password + "\r\n").encode())
        s += read_output()

    print_output(s)

    if not any(line.strip().endswith("#") for line in s.splitlines()):
        raise SystemExit("Could not enter privileged EXEC mode (#).")

    # --------------------------------------------------
    # Felles SSH-konfigurasjon
    # --------------------------------------------------

    common_commands = [
        f"hostname {hostname}",
        f"ip domain name {domain_name}",
        f"username {username} privilege 15 secret {password}",
        "crypto key generate rsa modulus 2048",
        "ip ssh version 2",
        "line vty 0 4",
        "login local",
        "transport input ssh",
        "exit",
    ]

    # --------------------------------------------------
    # Router eller switch
    # --------------------------------------------------

    if device_type == "router":
        # IP-en settes på Ethernet-porten som PC-en kobles til.
        router_commands = [
            "configure terminal",
            f"interface {interface_name}",
            f"ip address {device_ip} {subnet_mask}",
            "no shutdown",
            "exit",
        ]
        commands = router_commands + common_commands
    else:
        # Opprett VLAN-et og legg PC-porten i samme VLAN som management-IP-en.
        switch_commands = [
            "configure terminal",
            f"vlan {vlan_id}",
            "exit",
            f"interface vlan {vlan_id}",
            f"ip address {device_ip} {subnet_mask}",
            "no shutdown",
            "exit",
            f"interface {interface_name}",
            "switchport mode access",
            f"switchport access vlan {vlan_id}",
            "no shutdown",
            "exit",
        ]
        if gateway:
            switch_commands.append(f"ip default-gateway {gateway}")
        commands = switch_commands + common_commands

    # Unngå at statuskommandoene stopper på --More--.
    commands = ["terminal length 0"] + commands + ["end", "write memory"]

    # --------------------------------------------------
    # Send kommandoer
    # --------------------------------------------------

    print("\nStarting configuration...\n")

    for command in commands:
        if command.startswith("username "):
            print("Sending: [password command]")
        else:
            print(f"Sending: {command}")

        ser.write((command + "\r\n").encode())
        s = read_output(timeout=60 if command.startswith("crypto key") else 30)

        # Behold eksisterende RSA-nøkler hvis scriptet kjøres igjen.
        if command.startswith("crypto key") and "[yes/no]" in s.lower():
            ser.write(b"no\r\n")
            s += read_output()

        if command == "write memory" and "[confirm]" in s.lower():
            ser.write(b"\r\n")
            s += read_output()

        if command.startswith("username "):
            # Skjul hele svaret, også hvis passordet ekkoes over flere linjer.
            print("Device reply hidden for password command.")
        else:
            print_output(s)

        errors = ("% invalid", "% incomplete", "% ambiguous", "% error", "% bad", "% cannot", "overlaps with")
        if any(error in s.lower() for error in errors):
            raise SystemExit("Configuration stopped: the device reported an error.")

        if not any(line.strip().endswith("#") for line in s.splitlines()):
            raise SystemExit("Configuration stopped: no CLI prompt received.")

    # --------------------------------------------------
    # Vis grensesnitt og kontroller SSH
    # --------------------------------------------------

    ser.write(b"show ip interface brief\r\n")
    print_output(read_output())

    ser.write(b"show ip ssh\r\n")
    s = read_output()
    print_output(s)

    if "ssh enabled" not in s.lower():
        raise SystemExit("SSH could not be verified. Check the device output above.")

    print("\nConfiguration sent and saved. SSH is enabled.")
    print("Connect the Ethernet cable and check that the management interface is up/up.")
    print(f"PuTTY: SSH to {device_ip}, port 22. Username: {username}")

finally:
    # Lukk COM-porten også hvis scriptet stopper ved en feil.
    ser.close()