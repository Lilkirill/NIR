/system identity set name=mt-r0424
/interface ethernet add name=ether1 comment="WAN prepared case 424"
/interface ethernet add name=ether2 comment="LAN prepared case 424"
/ip address add address=10.1.169.1/30 interface=ether1
/ip address add address=172.18.174.1/24 interface=ether2
/ip route add dst-address=0.0.0.0/0 gateway=10.1.169.2
/ip service set ssh disabled=no
/user add name=admin group=full password="regression-secret"
