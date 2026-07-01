/system identity set name=mt-r0433
/interface ethernet add name=ether1 comment="WAN prepared case 433"
/interface ethernet add name=ether2 comment="LAN prepared case 433"
/ip address add address=10.1.178.1/30 interface=ether1
/ip address add address=172.18.183.1/24 interface=ether2
/ip route add dst-address=0.0.0.0/0 gateway=10.1.178.2
/ip service set ssh disabled=no
/user add name=netops group=full password="regression-secret"
