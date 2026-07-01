/system identity set name=mt-r0391
/interface ethernet add name=ether1 comment="WAN prepared case 391"
/interface ethernet add name=ether2 comment="LAN prepared case 391"
/ip address add address=10.1.136.1/30 interface=ether1
/ip address add address=172.18.141.1/24 interface=ether2
/ip service set ssh disabled=no
/user add name=admin group=full password="regression-secret"
