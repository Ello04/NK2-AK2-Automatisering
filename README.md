# NK2 – AK2: Automatisering

Python-script som setter opp SSH på en Cisco-router eller switch gjennom en konsollkabel. Etter oppsettet kobler du til med SSH over Ethernet.

## Du trenger

- Python3 på Windows eller Linux.
- En Cisco-router eller switch som støtter SSH.
- Konsollkabel og Ethernet-kabel.

## 1. Koble til konsollen

Koble konsollkabelen mellom PC-en og enheten. La enheten starte ferdig, og lukk PuTTY hvis det bruker samme serieport. Scriptet bruker 9600 baud og forventer en CLI-prompt eller initial configuration-dialogen.

Åpne en terminal i prosjektmappen.

## 2. Installer og kjør

### Windows – PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe ssh_setup.py
```

### Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python ssh_setup.py
```

Velg serieporten og `router` eller `switch`. Fyll inn hostname, brukernavn, passord, management-IP og riktig Ethernet-port. Standardverdier velges med Enter.

Portene finnes automatisk: for eksempel `COM1` på Windows og `/dev/ttyUSB0` på Linux. På Linux må brukeren ha tilgang til serieporten.

## 3. Koble til med SSH

Koble Ethernet-kabelen fra PC-en til porten du valgte i scriptet. Sett manuell IPv4 på PC-ens Ethernet-kort i samme subnett som enheten.

Eksempel:

| Innstilling | Enhet | PC |
|---|---|---|
| IP-adresse | `172.16.27.10` | `172.16.27.100` |
| Nettverksmaske | `255.255.255.0` | `255.255.255.0` |

Gateway og DNS kan stå tomt ved direkte tilkobling i denne laben.

Kjør i PowerShell eller Linux-terminalen:

```bash
ssh cisco@172.16.27.10
```

Bruk brukernavnet, management-IP-en og passordet du oppga i scriptet.

I PuTTY velger du **SSH**, enhetens management-IP og port **22**.

## Hvis det ikke fungerer

Kontroller gjennom konsollen:

```text
show ip interface brief
show ip ssh
```

Management-grensesnittet må vise `up/up`, og SSH skal vise `SSH Enabled - version 2.0`. Sjekk kabel, riktig port og PC-ens IP-adresse hvis SSH gir timeout.
