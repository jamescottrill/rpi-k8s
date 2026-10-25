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
	ansible-playbook -i host.ini site.yaml --tags k3s --limit master,k3snodes
#remove-children:
#	ansible k3snodes -a "bash /usr/local/bin/k3s-agent-uninstall.sh" -i host.ini
#remove-master:
#	ansible master -a "bash /usr/local/bin/k3s-uninstall.sh" -i host.ini
run:
	ansible-playbook -i host.ini site.yaml
upgrade:
	ansible-playbook -i host.ini upgrade.yaml