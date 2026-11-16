from netmiko import ConnectHandler
import getpass

paloalto = {
    'device_type': 'paloalto_panos',
    'host': '192.168.0.252',
    'username': 'admin',
    'password': getpass.getpass('Senha do Palo Alto: '),
}

conn = ConnectHandler(**paloalto)

# Envia o comando operacional para buscar a configuração
output = conn.send_command("show config running")

with open("palo_alto_completo.txt", "w", encoding="utf-8") as f:
    f.write(output)

print("Configuração salva em palo_alto_completo.txt")
conn.disconnect()