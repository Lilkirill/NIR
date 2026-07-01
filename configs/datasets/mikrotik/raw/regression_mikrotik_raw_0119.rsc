/system identity set name=mt-r0492
/interface ethernet add name=ether1 comment="WAN prepared case 492"
/interface ethernet add name=ether2 comment="LAN prepared case 492"
/ip address add address=10.1.237.1/30 interface=ether1
/ip address add address=172.18.242.1/24 interface=ether2
/ip route add dst-address=0.0.0.0/0 gateway=10.1.237.2
/ip service set ssh disabled=yes
/user add name=admin group=full password="regression-secret"
