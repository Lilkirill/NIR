/system identity set name=mt-core-1
/interface ethernet add name=ether1 comment="uplink"
/interface ethernet add name=ether2 comment="lan"
/ip address add address=10.10.10.1/30 interface=ether1
/ip address add address=192.168.88.1/24 interface=ether2
/ip route add dst-address=0.0.0.0/0 gateway=10.10.10.2
/ip service set ssh disabled=no
/user add name=admin group=full
