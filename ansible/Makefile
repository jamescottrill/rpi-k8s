source:
	source venv/bin/activate
requirements:
	pip install -r requirements.txt
install-traefik:
	cd hc-traefik && make install
install-certmanager:
	cd hc-certmanager && make install
setup:
	ansible all -m get_url -a "url=https://get.k3s.io dest=/tmp/k3s mode=0755" -i host.ini
	ansible rpi1 -e INSTALL_K3S_EXEC=--disable=servicelb -e K3S_KUBECONFIG_MODE=644 -a "bash /tmp/k3s" -v -i host.ini
children:
	TOKEN=$(ssh rpi-1 "sudo cat /var/lib/rancher/k3s/server/node-token")
	ansible rpi5 -m get_url -a "url=https://get.k3s.io dest=/tmp/k3s mode=0755" -i host.ini
	ansible rpi5 -e K3S_TOKEN="K109d2400f3dd5908bea06b27bf5449d7956c8f253c3a0ee5324b7f8014e3ae846a::server:4999f2e2f677474728d2294e95f1fda3" -e K3S_URL="https://192.168.0.100:6443" -e K3S_NODE_NAME={{inventory_hostname}} -a "bash /tmp/k3s" -v -i host.ini
#remove-children:
#	ansible k3snodes -a "bash /usr/local/bin/k3s-agent-uninstall.sh" -i host.ini
#remove-master:
#	ansible master -a "bash /usr/local/bin/k3s-uninstall.sh" -i host.ini
run:
	ansible-playbook -i host.ini site.yaml
upgrade:
	ansible-playbook -i host.ini upgrade.yaml