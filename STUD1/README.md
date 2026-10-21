# NK2 – Arbeidskrav 2: STUD1

Python konfigurerer SSH via konsollkabel fra Windows. Ansible kjører fra
WSL på samme PC og setter opp VLAN, DHCP, ruting og EtherChannel via Ethernet.

## Status

- SSH er satt opp på alle fem enhetene.
- Ansible-oppsettet har fullført uten feil på alle fem, fordelt på flere kjøringer.
- Sluttkontrollen mot alle fem fullførte uten `failed` eller `unreachable`.
- SW02 sin uplink ble manuelt rettet til trunk før siste vellykkede kjøring.
- DHCP-tildeling og trafikk mellom klienter er ikke testet: klient-PC-er mangler.
- EtherChannel mot STUD2 er konfigurert, men avslått og ikke testet med motpart.

Denne utgaven lar Python klargjøre trunk på uplinkene og lar Ansible vente
på SSH-porten før de nederste switchene konfigureres. Disse siste endringene
er kontrollert lokalt, men et helt nytt oppsett fra reset er ikke testet med dem.
**Utstyret som allerede fungerer, trenger ikke resettes eller kjøres gjennom Python igjen.**

## IP-plan

Alle management-adressene bruker nettmasken `255.255.255.0`.

| Enhet | Modell | Management-IP | Gateway |
|---|---|---|---|
| PC | Windows med WSL | 172.16.27.100 | 172.16.27.10 |
| Multilayer01 | Catalyst C9300L-24T-4G | 172.16.27.12 | 172.16.27.10 |
| Router01 | ISR4221 | 172.16.27.10 | – |
| Router02 | Cisco 2901 | 172.16.27.11 | – |
| SW01 | Catalyst 2960 | 172.16.28.11 | 172.16.28.1 |
| SW02 | Catalyst 1000 | 172.16.28.12 | 172.16.28.1 |

Sett PC-adressen på **Ethernet-kortet i Windows**. WSL bruker forbindelsen
via Windows. `.27` ligger på PC-siden av routerne. `.28` ligger mot SW01
og SW02. Dette er et designvalg for to rutede nettverk, ikke bestemte
IP-adresser som oppgaven krever.

## Kabling

| Fra | Til |
|---|---|
| PC | Multilayer01 Gi1/0/3 |
| Multilayer01 Gi1/0/1 | Router01 Gi0/0/1 |
| Multilayer01 Gi1/0/2 | Router02 Gi0/1 |
| Router01 Gi0/0/0 | SW01 Fa0/3 |
| Router02 Gi0/0 | SW01 Fa0/4 |
| SW01 Fa0/2 | SW02 Gi1/0/3 |
| SW02 Gi1/0/1 | Klient i VLAN 10, når tilgjengelig |
| SW02 Gi1/0/2 | Klient i VLAN 20, når tilgjengelig |
| SW02 Gi1/0/4 og Gi1/0/5 | EtherChannel mot STUD2 |

## 1. SSH via konsoll – ved nytt oppsett

Kjør i prosjektmappen i Windows. Lukk PuTTY først, slik at serieporten er ledig.

```powershell
python -m pip install -r requirements.txt
python ssh_setup.py
```

Velg riktig COM-port. Kjør på én enhet om gangen. Bruk samme SSH-brukernavn
(`cisco` i eksemplene) og passord på alle fem. Passord er ikke lagret i filene.
Scriptet håndterer oppstartsspørsmål og går til privileged EXEC før konfigurering.

Bruk IP og gateway fra tabellen over, samt disse valgene:

| Enhet | Device type | Port | Management VLAN | Port mode |
|---|---|---|---|---|
| Multilayer01 | switch | GigabitEthernet1/0/3 | 1 | access |
| Router01 | router | GigabitEthernet0/0/1 | – | – |
| Router02 | router | GigabitEthernet0/1 | – | – |
| SW01 | switch | FastEthernet0/3 | 99 | trunk |
| SW02 | switch | GigabitEthernet1/0/3 | 99 | trunk |

På trunkporten tillater Python management-VLAN-et og setter det som native
VLAN. Ansible legger til klient-VLAN og de øvrige trunkportene senere.
Denne delen er tilpasset switchmodellene i tabellen.

Scriptet er ikke en fabrikkreset. Ved gjenbruk av utstyr må gammel
konfigurasjon vurderes først. I denne laben ble gammel `172.16.27.13` på
SW01 sitt VLAN 1 fjernet via konsollen:

```text
configure terminal
interface vlan 1
no ip address
end
write memory
```

## 2. Ansible i WSL

Legg hele prosjektmappen i `~/STUD1`. Windows og WSL har separate Python-miljøer.
Ved første installasjon:

```bash
cd ~/STUD1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-ansible.txt
ansible-galaxy collection install -r collections.yml
```

Paramiko er begrenset til versjon under 5 fordi Router02 tilbyr eldre
SSH-algoritmer. Ansible- og collection-versjonene er satt til versjonene
som ble brukt i laben. Ved en ny terminal må miljøet aktiveres igjen:

```bash
cd ~/STUD1
source .venv/bin/activate
```

Koble PC-en til labnettet med IPv4-innstillingene over. Kontroller først:

```bash
ansible-playbook -i inventory.yml oppsett.yml --syntax-check
ansible-playbook -i inventory.yml kontroll.yml --limit 'management_switch:routers' -u cisco --ask-pass
```

`kontroll.yml` kjører bare statuskommandoer. Når de tre øverste enhetene
svarer uten feil, kjør oppsettet:

```bash
ansible-playbook -i inventory.yml oppsett.yml -u cisco --ask-pass
```

Rekkefølgen er **Multilayer01 → routerne → SW01 → SW02**. SW01 og SW02
blir først tilgjengelige fra PC-en når routerne og uplinkene er klargjort.
Ansible venter inntil tre minutter på SSH-porten til hver nedre switch.
Ventingen bekrefter TCP-tilgang, ikke vellykket innlogging.

Brukeren opprettes med privilege 15. Dersom enheten krever eget
enable-passord, legg til `--ask-become-pass`.

| VLAN | Nettverk | Gateway / DHCP |
|---|---|---|
| 10 | 192.168.10.0/24 | Router01: 192.168.10.1 |
| 20 | 192.168.20.0/24 | Router02: 192.168.20.1 |
| 99 | 172.16.28.0/24 | Management: Router01 .1, Router02 .2 |

VLAN 99 ligger på Router01 `Gi0/0/0.99` og Router02 `Gi0/0.99`.
De fysiske dataportene har ingen IP. Statiske ruter forbinder klientnettene.
DHCP reserverer `.1` til `.20`. Oppsettet inkluderer ikke internettilgang eller DNS.

EtherChannel er avslått med `etherchannel_enabled: false`. Avtal IP-plan,
DHCP, VLAN og LACP med STUD2 før aktivering. Trunken tillater VLAN 10 og 20
med native VLAN 1. Unngå like gateway-adresser og overlappende DHCP-pooler.
Sett verdien til `true` først når begge sider er klare. Jobber du alene,
beholder du `false`.

## 3. Sluttkontroll

```bash
ansible-playbook -i inventory.yml kontroll.yml -u cisco --ask-pass
```

Alle fem skal ha `failed=0` og `unreachable=0`. Kontroller også at
adressene, trunkene og rutene i utskriften stemmer. En grønn kjøring
betyr at statuskommandoene lyktes, ikke at klienttrafikken er testet.

Når klienter blir tilgjengelige: bruk automatisk IPv4, kontroller DHCP-adresse,
ping gateway og test mellom VLAN 10 og 20. Ta vare på resultatene til innleveringen.

## Vanlig SSH fra WSL

```bash
ssh cisco@172.16.27.12
ssh cisco@172.16.27.10
ssh cisco@172.16.27.11
ssh cisco@172.16.28.11
ssh cisco@172.16.28.12
```

Router02 trenger dette vertsavgrensede unntaket i `~/.ssh/config`:

```sshconfig
Host 172.16.27.11
    User cisco
    KexAlgorithms +diffie-hellman-group14-sha1
    HostKeyAlgorithms +ssh-rsa
```

Dette gjelder OpenSSH. Ansible bruker Paramiko-versjonen fra requirements-filen.

## Filer og innlevering

- `ssh_setup.py`: SSH og management via konsoll.
- `inventory.yml`: enhetsnavn, IP-adresser, porter og VLAN-variabler.
- `oppsett.yml`: nettverkskonfigurasjon og lagring.
- `kontroll.yml`: lesekontroll.
- `requirements.txt`: Python-pakker for konsollscriptet.
- `requirements-ansible.txt`, `collections.yml`, `ansible.cfg`: Ansible-miljøet.

Last opp filene, inkludert `.gitignore`, i et offentlig GitHub-repo.
Ikke last opp virtuelle miljøer, passord eller `:Zone.Identifier`-filer.
Repoet er ikke publisert automatisk fra denne pakken.
