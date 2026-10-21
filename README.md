# NK2 – Arbeidskrav 2: STUD1

Python setter opp SSH via konsollkabel fra **Windows**.
Ansible kjøres fra **WSL på samme PC** og konfigurerer nettverket via Ethernet.

SSH er nå konfigurert på alle fem enhetene. Ansible-oppsettet og DHCP er
foreløpig ikke bekreftet testet i racket.

## Adresser og porter

Alle management-adressene bruker nettmasken `255.255.255.0`.
Brukernavnet er `cisco`. Passord skrives inn når scriptet eller Ansible spør.

| Enhet | Navn i inventory | Management-IP | Port i Python | VLAN | Gateway |
|---|---|---|---|---|---|
| Router01 (ISR4221) | R1 | 172.16.27.10 | GigabitEthernet0/0/1 | – | – |
| Router02 (2901) | R2 | 172.16.27.11 | GigabitEthernet0/1 | – | – |
| Multilayer01 (C9300L) | SW_MGMT | 172.16.27.12 | GigabitEthernet1/0/3 | 1 | 172.16.27.10 |
| SW02 | SW1 | 172.16.28.11 | FastEthernet0/3* | 99 | 172.16.28.1 |
| SW02 | SW2 | 172.16.28.12 | GigabitEthernet1/0/3 | 99 | 172.16.28.1 |

*Portnavnene på SW1 er fortsatt fra diagrammet og må kontrolleres mot fysisk utstyr.
Navnene i inventory er Ansible-aliaser og trenger ikke være identiske med hostname.

Sett Ethernet-kortet i **Windows** til:

- IP: `172.16.27.100`
- Nettmaske: `255.255.255.0`
- Gateway: `172.16.27.10`

`.27` brukes mellom PC-en, øverste switch og routerne. `.28` brukes mellom
routerne og de nederste switchene. Dette er et designvalg for de separate
rutede forbindelsene, ikke et krav om bestemte adresser fra oppgaven.

Ansible setter `172.16.28.1` på R1 sitt `Gi0/0/0.99` og `172.16.28.2`
på R2 sitt `Gi0/0.99`. De fysiske dataportene har ikke egne IP-adresser.

## Kabling

| Fra | Til |
|---|---|
| Management-PC | Multilayer01 Gi1/0/3 |
| Multilayer01 Gi1/0/1 | Router01 Gi0/0/1 |
| Multilayer01 Gi1/0/2 | Router02 Gi0/1 |
| Router01 Gi0/0/0 | SW1 Fa0/3* |
| Router02 Gi0/0 | SW1 Fa0/4* |
| SW1 Fa0/2* | SW02 Gi1/0/3 |
| SW02 Gi1/0/1 | Klient i VLAN 10 |
| SW02 Gi1/0/2 | Klient i VLAN 20 |
| SW02 Gi1/0/4 og Gi1/0/5 | EtherChannel mot STUD2 |

## Python via konsoll – allerede gjennomført

Fra prosjektmappen i Windows:

```powershell
python -m pip install -r requirements.txt
python ssh_setup.py
```

Lukk PuTTY før kjøring slik at COM-porten er ledig. Kjør på én enhet om
gangen, med verdiene i tabellen. På SW1 og SW02 velges uplinken når
scriptet spør etter «Switch port connected to PC».

Scriptet håndterer initial configuration-dialogen og setter opp lokal
bruker, SSH, management-IP og switchport. PC-ens IP-adresse har ingen
betydning for selve konsollforbindelsen.

## Ansible fra WSL – neste steg

Prosjektet ligger i `~/STUD1`, altså `/home/ditt-brukernavn/STUD1`.
Windows og WSL har separate virtuelle Python-miljøer.

Disse installasjonskommandoene er allerede kjørt i WSL:

```bash
cd ~/STUD1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-ansible.txt
ansible-galaxy collection install -r collections.yml
```

### Kontroller inventory før første kjøring

Den opprinnelige `inventory.yml` har andre portnavn for R2 og SW2.
**Denne README-oppdateringen endrer ikke inventory-filen.**

På verten `R2` legges disse variablene under `ansible_host`, med samme innrykk:

```yaml
management_port: GigabitEthernet0/1
data_port: GigabitEthernet0/0
```

Disse overstyrer gruppens portnavn, som fortsatt gjelder for R1.
På `SW2` skal portene være:

```yaml
trunk_ports:
  - GigabitEthernet1/0/3
client_ports:
  - {port: GigabitEthernet1/0/1, vlan: 10}
  - {port: GigabitEthernet1/0/2, vlan: 20}
etherchannel_ports:
  - GigabitEthernet1/0/4
  - GigabitEthernet1/0/5
```

Kontroller også SW1 sine portnavn med `show interfaces status` via konsollen.
Tilpass inventory og kablingstabellen dersom navnene er annerledes.

### Kjør oppsettet

Aktiver miljøet og test SSH fra WSL:

```bash
cd ~/STUD1
source .venv/bin/activate
ssh cisco@172.16.27.10
```

Skriv `exit` når du er inne. Test gjerne også `.27.11` og `.27.12`.
SW1 og SW2 blir tilgjengelige fra PC-en under Ansible-kjøringen når
routerne og trunkforbindelsene er konfigurert.

Når SSH er satt opp på alle fem og inventory stemmer, kjør hele playbooken én gang:

```bash
ansible-playbook -i inventory.yml oppsett.yml -u cisco --ask-pass
```

Skriv SSH-passordet når du blir spurt. Brukeren har privilege 15.
Hvis enheten krever et eget enable-passord, legg til `--ask-become-pass`.

Rekkefølgen er **SW_MGMT → routerne → SW1 → SW2**.
Playbooken konfigurerer og lagrer VLAN, trunkporter, klientporter,
routerundergrensesnitt, DHCP og statiske ruter.

| Klient-VLAN | Nettverk | Gateway og DHCP-server |
|---|---|---|
| 10 | 192.168.10.0/24 | R1: 192.168.10.1 |
| 20 | 192.168.20.0/24 | R2: 192.168.20.1 |

DHCP reserverer `.1` til `.20`. Internettilgang og DNS konfigureres ikke.

EtherChannel mot STUD2 er avslått med `etherchannel_enabled: false`.
Avtal VLAN, IP-adresser, DHCP og LACP med STUD2 før aktivering.
Forbindelsen tillater VLAN 10 og 20, med native VLAN 1. Unngå dupliserte
IP-adresser og overlappende DHCP-pooler. Sett verdien til `true` når begge
sider er klare, og kjør playbooken igjen. Jobber du alene, behold `false`.

## Kontroller resultatet

```bash
ansible-playbook -i inventory.yml kontroll.yml -u cisco --ask-pass
```

Sett klientene til automatisk IPv4 (DHCP). Kontroller adressene og test
ping til gateway og mellom klientene i VLAN 10 og 20.
Kontroll-playbooken viser status, men utfører ikke disse ping-testene.

Vanlig CLI-tilgang: `ssh cisco@172.16.27.10`, eller PuTTY med SSH og port 22.

## GitHub

Last opp prosjektfilene og `.gitignore` i et offentlig repository.
Ikke last opp `.venv`, passord eller filer med suffikset `:Zone.Identifier`.
Dokumenter faktiske testresultater etter at Ansible og DHCP er testet.
