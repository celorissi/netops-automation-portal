from panos.firewall import Firewall
from panos.network import (
    TunnelInterface,
    IkeGateway,
    IpsecTunnel,
    IpsecCryptoProfile,
    IkeCryptoProfile,
    Zone,
    StaticRoute,
    VirtualRouter,
)
from panos.policies import SecurityRule, Rulebase
import config_vpn


def configurar_vpn_paloalto(host, user, password):
    fw = Firewall(host=host, user=user, password=password)
    resultados = {}

    try:
        # 1. Interface de Túnel
        tunnel = TunnelInterface(name="tunnel.1", ip=[f"{config_vpn.PALOALTO_TUNNEL_IP}/30"])
        fw.add(tunnel)
        tunnel.create()
        resultados["interface_tunel"] = "OK"

        # 2. Zona e Associação
        zona = Zone(name="VPN-ZONE", mode="layer3", interface=["tunnel.1"])
        fw.add(zona)
        zona.create()
        resultados["zona"] = "OK"

        # 3. Perfil IKE Crypto
        prop1 = config_vpn.PHASE1_PROPOSAL
        ike_prof = IkeCryptoProfile(
            name=config_vpn.TUNNEL_NAME,
            dh_group=[f"group{prop1['dh_group']}"],
            authentication=[prop1["hash"]],
            encryption=[prop1["encryption"]],
            lifetime_seconds=prop1["lifetime_seconds"],
        )
        fw.add(ike_prof)
        ike_prof.create()
        resultados["ike_crypto_profile"] = "OK"

        # 4. IKE Gateway
        gw = IkeGateway(
            name=config_vpn.TUNNEL_NAME,
            version="ikev2",
            interface="ethernet1/2",
            local_ip_address_type="ip",
            local_ip_address=f"{config_vpn.PALOALTO_WAN_IP}/30",
            peer_ip_type="ip",
            peer_ip_value=config_vpn.FORTIGATE_WAN_IP,
            auth_type="pre-shared-key",
            pre_shared_key=config_vpn.IPSEC_PSK,
            ikev2_crypto_profile=config_vpn.TUNNEL_NAME,
        )
        fw.add(gw)
        gw.create()
        resultados["ike_gateway"] = "OK"

        # 5. Perfil IPsec Crypto
        prop2 = config_vpn.PHASE2_PROPOSAL
        ipsec_prof = IpsecCryptoProfile(
            name=config_vpn.TUNNEL_NAME,
            esp_encryption=[prop2["encryption"]],
            esp_authentication=[prop2["authentication"]],
            dh_group=f"group{prop2['pfs_group']}",
            lifetime_seconds=prop2["lifetime_seconds"],
        )
        fw.add(ipsec_prof)
        ipsec_prof.create()
        resultados["ipsec_crypto_profile"] = "OK"

        # 6. Túnel IPsec
        tunel = IpsecTunnel(
            name=config_vpn.TUNNEL_NAME,
            tunnel_interface="tunnel.1",
            ak_ike_gateway=config_vpn.TUNNEL_NAME,
            ak_ipsec_crypto_profile=config_vpn.TUNNEL_NAME,
        )
        fw.add(tunel)
        tunel.create()
        resultados["ipsec_tunnel"] = "OK"

        # 7. Virtual Router e Rota Estática
        vr = VirtualRouter(name="default")
        fw.add(vr)
        vr.refresh()
        interfaces_atuais = list(vr.interface) if vr.interface else []
        if "tunnel.1" not in interfaces_atuais:
            interfaces_atuais.append("tunnel.1")
            vr.interface = interfaces_atuais
            vr.apply()

        rota = StaticRoute(
            name=config_vpn.TUNNEL_NAME,
            destination=config_vpn.FORTIGATE_LOCAL_NETWORK,
            interface="tunnel.1",
            nexthop_type="ip-address",
            nexthop=config_vpn.FORTIGATE_TUNNEL_IP,
        )
        vr.add(rota)
        rota.create()
        resultados["rota_estatica"] = "OK"

        # 8. Políticas de Segurança
        rb = Rulebase()
        fw.add(rb)
        r_out = SecurityRule(
            name=f"{config_vpn.TUNNEL_NAME}_OUT",
            fromzone=["LAN-ZONE"],
            tozone=["VPN-ZONE"],
            source=["any"],
            destination=["any"],
            application=["any"],
            service=["any"],
            action="allow",
        )
        r_in = SecurityRule(
            name=f"{config_vpn.TUNNEL_NAME}_IN",
            fromzone=["VPN-ZONE"],
            tozone=["LAN-ZONE"],
            source=["any"],
            destination=["any"],
            application=["any"],
            service=["any"],
            action="allow",
        )
        rb.add(r_out)
        rb.add(r_in)
        r_out.create()
        r_in.create()
        resultados["politicas"] = "OK"

        # 9. Commit
        fw.commit(sync=True)
        resultados["commit"] = "OK"
        resultados["status"] = "Sucesso"
    except Exception as e:
        resultados["status"] = f"Erro: {e}"

    return resultados