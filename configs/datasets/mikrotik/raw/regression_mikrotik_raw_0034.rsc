/system identity set name=mt-r0407
/interface ethernet add name=ether1 comment="WAN prepared case 407"
/interface ethernet add name=ether2 comment="LAN prepared case 407"
/ip address add address=10.1.152.1/30 interface=ether1
/ip address add address=172.18.157.1/24 interface=ether2
/ip route add dst-address=0.0.0.0/0 gateway=10.1.152.2
/ip service set ssh disabled=yes
/user add name=admin group=full password="regression-secret"
