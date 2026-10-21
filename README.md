# NK2 – Arbeidskrav 2: STUD1

Python setter opp SSH via konsollkabel. Ansible setter opp VLAN, DHCP,
ruting og EtherChannel via Ethernet. Oppsettet bruker R1, R2, SW_MGMT
(øverst), SW1 (midten) og SW2 (nederst) i STUD1.

IP-adressene er et forslag. Endre adresser og porter i `inventory.yml`
dersom racket ditt er annerledes. Oppsettet er laget for labutstyr med
grunnkonfigurasjon, ikke for å erstatte en vilkårlig eksisterende konfigurasjon.

## 1. Koble kablene

| Fra | Til |
|---|---|
| Management-PC | SW_MGMT Gi1/0/3 |
| Multilayer01 Gi1/0/1 | R01 Gi0/0/1 |
| Multilayer01 Gi1/0/2 | R02 Gi0/0/1 |
| R01 Gi0/0/0 | SW01 Fa0/3 |
| R02 Gi0/0/0 | SW01 Fa0/4 |
| SW01 Fa0/2 | SW02 Fa0/3 |
| SW02 Fa0/1 | Klient i VLAN 10 |
| SW02 Fa0/2 | Klient i VLAN 20 |
| SW02 Fa0/4 og Fa0/5 | EtherChannel mot STUD2 |

Sett manuell IPv4 på management-PC-ens Ethernet-kort:

- IP: `172.16.27.100`
- Nettmaske: `255.255.255.0`
- Gateway: `172.16.27.10`

## 2. Sett opp SSH med Python

Installer pakkene og kjør scriptet fra prosjektmappen:

```bash
python -m pip install -r requirements.txt
python ssh_setup.py
```

På Linux kan kommandoen hete `python3`. Bruk et virtuelt miljø ved behov.
Brukeren må ha tilgang til serieporten på Linux. Lukk PuTTY-konsollen
før scriptet kjører, slik at serieporten er ledig.

Koble konsollkabelen til én enhet om gangen. Velg riktig serieport og
bruk verdiene under. Bruk samme SSH-brukernavn og passord på alle fem.
Nettmasken er `255.255.255.0` på alle enhetene.

| Hostname | Type | Management-IP | Port i Python | VLAN | Gateway |
|---|---|---|---|---|---|
| SW_MGMT | switch | 172.16.27.12 | GigabitEthernet1/0/3 | 1 | Tomt |
| R1 | router | 172.16.27.10 | GigabitEthernet0/0/1 | – | – |
| R2 | router | 172.16.27.11 | GigabitEthernet0/0/1 | – | – |
| SW1 | switch | 172.16.28.11 | FastEthernet0/3 | 99 | 172.16.28.1 |
| SW2 | switch | 172.16.28.12 | FastEthernet0/3 | 99 | 172.16.28.1 |

For SW1 og SW2 velger du uplinken Fa0/3 når scriptet spør etter
«Switch port connected to PC». Ansible gjør denne om til trunk senere.
Disse to switchene blir tilgjengelige fra management-PC-en under Ansible-kjøringen.

Routerens management-IP må ligge på **Gi0/0/1**. Hvis du tidligere satte
den på Gi0/0/0, fjern IP-en der via konsollen før du kjører Python på nytt:

```text
enable
configure terminal
interface GigabitEthernet0/0/0
no ip address
end
```

## 3. Kjør Ansible fra Linux eller WSL

Ansible kjøres fra management-PC-en. Ved WSL: legg prosjektmappen i
Linux-hjemmemappen. Kontroller at Linux/WSL kan nå `172.16.27.10`.

Fra prosjektmappen:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-ansible.txt
ansible-galaxy collection install -r collections.yml
ansible-playbook -i inventory.yml oppsett.yml -u cisco --ask-pass
```

Bytt `cisco` med brukernavnet du valgte. Skriv SSH-passordet når du blir spurt.
Python oppretter brukeren med privilege 15. Hvis utstyret likevel krever
et eget enable-passord, legg til `--ask-become-pass`.

Kjør hele `oppsett.yml` første gang. Den konfigurerer SW_MGMT, routerne,
SW1 og SW2 i riktig rekkefølge og lagrer konfigurasjonen.

| VLAN | Nettverk | Gateway / DHCP-server |
|---|---|---|
| 10 | 192.168.10.0/24 | R1: 192.168.10.1 |
| 20 | 192.168.20.0/24 | R2: 192.168.20.1 |
| 99 | 172.16.28.0/24 | Management av SW1 og SW2 |

R1 og R2 deler DHCP-ansvaret: én router per klient-VLAN. Adressene
`.1` til `.20` er reservert. Statiske ruter gir forbindelse mellom klientnettene.
Dette oppsettet konfigurerer ikke internettilgang eller DNS.

EtherChannel mot STUD2 er avslått som standard. Avtal felles VLAN-, IP-,
DHCP- og LACP-oppsett med STUD2 før dere kobler sammen nettene. Begge
sider må tillate VLAN 10 og 20 og bruke samme native VLAN (her 1).
Unngå overlappende DHCP-pooler og like gateway-adresser.
Sett deretter `etherchannel_enabled: true` i `inventory.yml` og kjør igjen.
Jobber du alene, lar du den stå `false`.

## 4. Kontroller

```bash
ansible-playbook -i inventory.yml kontroll.yml -u cisco --ask-pass
```

Sett klientene til automatisk IPv4 (DHCP). Kontroller at de får adresse
i riktig VLAN, og test ping til gateway og en klient i det andre VLAN-et.
Kontroll-playbooken viser status; den utfører ikke disse ping-testene.

For vanlig CLI-tilgang fra management-PC-en:

```bash
ssh cisco@172.16.27.10
```

Alternativt: PuTTY → SSH → IP-adresse → port 22.

Pakken er kontrollert for Python-/YAML-syntaks, variabler og IP-plan.
Konsollleseren er testet med simulerte svar. Full Ansible-syntakskontroll
var blokkert fordi Cisco-collectionen ikke kunne lastes ned i testmiljøet.
Oppsettet er ikke testet på fysisk utstyr.

## GitHub

Opprett et offentlig repository og last opp filene i denne mappen,
inkludert `.gitignore`. Ikke last opp `.venv` eller passord.
Tilpass README til portene, adressene og testresultatene du faktisk bruker.

Dokumentasjon: [pySerial](https://pyserial.readthedocs.io/),
[Cisco IOS collection](https://docs.ansible.com/projects/ansible/latest/collections/cisco/ios/).
