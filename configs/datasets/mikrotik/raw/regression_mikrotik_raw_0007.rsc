/system identity set name=mt-r0380
/interface ethernet add name=ether1 comment="WAN prepared case 380"
/interface ethernet add name=ether2 comment="LAN prepared case 380"
/ip address add address=10.1.125.1/30 interface=ether1
/ip address add address=172.18.130.1/24 interface=ether2
/ip route add dst-address=0.0.0.0/0 gateway=10.1.125.2
/ip service set ssh disabled=no
/user add name=admin group=full password="regression-secret"
