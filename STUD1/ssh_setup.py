import pwinput
import serial
from serial.tools import list_ports
import time
import re


# Passordene brukes også til å skjule passord i konsollens svar.
password = ""
enable_password = ""


def has_prompt(output, privileged=False):
    ending = "#" if privileged else "[>#]"
    return bool(re.search(r"(?m)^[\w.-]+(?:\([^\r\n()]*\))?" + ending + r"\s*$", output))


def read_output(timeout=30):
    """Les til en CLI-prompt eller et spørsmål, i maksimalt timeout sekunder."""
    output = ""
    deadline = time.monotonic() + timeout
    last_received = time.monotonic()

    while time.monotonic() < deadline:
        if ser.in_waiting:
            output += ser.read(ser.in_waiting).decode(errors="ignore")
            last_received = time.monotonic()

        # Vent til svaret har roet seg. Tillat oppstartslogger etter prompten.
        if output.strip() and time.monotonic() - last_received >= 0.3:
            last_line = output.strip().splitlines()[-1].lower() if output.strip() else ""
            if has_prompt(output):
                return output
            questions = ("password:", "[yes/no]", "[yes]", "[confirm]", "press return")
            if any(question in last_line for question in questions):
                return output

        time.sleep(0.1)

    return output


def wait_for_cli(timeout=120):
    """Svar på oppstartsspørsmål og vent til routeren/switchens CLI er klar."""
    print("\nWaiting for device startup (up to 120 seconds)...")
    deadline = time.monotonic() + timeout
    ser.write(b"\r")

    while time.monotonic() < deadline:
        output = read_output(timeout=min(5, deadline - time.monotonic()))
        print_output(output)

        if has_prompt(output):
            return output

        # Flere spørsmål kan komme i samme svar. Håndter det siste.
        text = output.lower()
        questions = {
            "initial configuration": b"no\r",
            "terminate autoinstall": b"yes\r",
            "press return": b"\r",
        }
        latest = max(questions, key=lambda question: text.rfind(question))
        if text.rfind(latest) >= 0:
            ser.write(questions[latest])
        elif "username:" in text or "password:" in text:
            raise SystemExit("Console login required. Log in using PuTTY first, then close PuTTY and rerun.")
        else:
            # Oppstartslogger kan komme etter Press RETURN. Be om prompt igjen.
            ser.write(b"\r")

    raise SystemExit("No CLI prompt after 120 seconds. Check the console in PuTTY.")


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


def enter_privileged_exec(previous_output=None, timeout=180):
    """Hent fersk prompt og vent på EXEC selv om day0/PnP fortsatt starter."""
    global enable_password

    print("\nWaiting for privileged EXEC mode...")
    deadline = time.monotonic() + timeout
    password_sent = False
    enable_attempts = 0

    # Prompten fra før brukerinput kan være gammel. Be om en ny.
    ser.write(b"\r")
    while time.monotonic() < deadline:
        output = read_output(timeout=min(5, deadline - time.monotonic()))
        print_output(output)
        text = output.lower()

        if "password:" in text:
            if password_sent:
                raise SystemExit("Enable password was not accepted. Configuration stopped.")
            enable_password = pwinput.pwinput("Existing enable password: ")
            ser.write((enable_password + "\r").encode())
            password_sent = True
            continue

        # Bruk siste prompt dersom flere ligger i samme svar.
        prompts = re.findall(r"(?m)^([\w.-]+(?:\([^\r\n()]*\))?[>#])\s*$", output)
        prompt = prompts[-1] if prompts else ""
        if re.fullmatch(r"[\w.-]+#", prompt):
            return
        if "(config" in prompt:
            ser.write(b"end\r")
        elif prompt.endswith(">"):
            if password_sent or enable_attempts >= 3:
                raise SystemExit("Could not enter privileged EXEC. Check enable access.")
            ser.write(b"enable\r")
            enable_attempts += 1
        elif "press return" in text:
            ser.write(b"\r")
        elif "initial configuration" in text:
            ser.write(b"no\r")
        elif "terminate autoinstall" in text:
            ser.write(b"yes\r")
        elif "username:" in text:
            raise SystemExit("Console login required. Check the console in PuTTY.")
        elif password_sent:
            # Ikke send et tomt passord mens innloggingen behandles.
            continue
        else:
            # Under day0/PnP kan enable bli ignorert. Vent og be om prompt igjen.
            ser.write(b"\r")

    raise SystemExit("No privileged EXEC prompt after 180 seconds. Check the console in PuTTY.")


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

    startup_output = wait_for_cli()

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
        interface_name = required_input("Management Ethernet interface (2901: GigabitEthernet0/1; ISR4221: GigabitEthernet0/0/1): ")
    else:
        interface_name = required_input("Switch management port/uplink (example: GigabitEthernet1/0/3): ")
        vlan_id = input("Management VLAN [1]: ").strip() or "1"
        gateway = required_input("Management default gateway: ")
        while True:
            port_mode = input("Port mode: access for PC, trunk for uplink [access]: ").strip().lower() or "access"
            if port_mode in ("access", "trunk"):
                break
            print("Please enter access or trunk.")

    # --------------------------------------------------
    # Gå til privileged EXEC før konfigurasjon
    # --------------------------------------------------

    enter_privileged_exec(startup_output)

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
        # Uplinker klargjøres som trunk før Ansible, med management som native VLAN.
        switch_commands = [
            "configure terminal",
            f"vlan {vlan_id}",
            "exit",
            f"interface vlan {vlan_id}",
            f"ip address {device_ip} {subnet_mask}",
            "no shutdown",
            "exit",
            f"interface {interface_name}",
        ]
        if port_mode == "trunk":
            switch_commands += [
                f"switchport trunk native vlan {vlan_id}",
                f"switchport trunk allowed vlan {vlan_id}",
                "switchport mode trunk",
            ]
        else:
            switch_commands += [
                "switchport mode access",
                f"switchport access vlan {vlan_id}",
            ]
        switch_commands += ["no shutdown", "exit"]
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

        ser.write((command + "\r").encode())
        s = read_output(timeout=60 if command.startswith("crypto key") else 30)

        # Behold eksisterende RSA-nøkler hvis scriptet kjøres igjen.
        if command.startswith("crypto key") and "[yes/no]" in s.lower():
            ser.write(b"no\r")
            s += read_output()

        if command == "write memory" and "[confirm]" in s.lower():
            ser.write(b"\r")
            s += read_output()

        if command.startswith("username "):
            # Skjul hele svaret, også hvis passordet ekkoes over flere linjer.
            print("Device reply hidden for password command.")
        else:
            print_output(s)

        errors = ("% invalid", "% incomplete", "% ambiguous", "% error", "% bad", "% cannot", "overlaps with")
        if any(error in s.lower() for error in errors):
            raise SystemExit("Configuration stopped: the device reported an error.")

        if not has_prompt(s, privileged=True):
            raise SystemExit("Configuration stopped: no CLI prompt received.")

    # --------------------------------------------------
    # Vis grensesnitt og kontroller SSH
    # --------------------------------------------------

    ser.write(b"show ip interface brief\r")
    print_output(read_output())

    ser.write(b"show ip ssh\r")
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
