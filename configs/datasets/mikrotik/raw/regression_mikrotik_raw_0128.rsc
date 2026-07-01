/system identity set name=mt-r0501
/interface ethernet add name=ether1 comment="WAN prepared case 501"
/interface ethernet add name=ether2 comment="LAN prepared case 501"
/ip address add address=10.1.246.1/30 interface=ether1
/ip address add address=172.18.1.1/24 interface=ether2
/ip service set ssh disabled=no
/user add name=admin group=full password="regression-secret"
