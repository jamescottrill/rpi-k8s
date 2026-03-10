install:
	helm upgrade --install longhorn . -n longhorn-system --create-namespace
uninstall:
	helm uninstall longhorn -n longhorn-system
prereqs:
	ansible all -m apt -a "name=open-iscsi,nfs-common state=present" -i ../ansible/host.ini --become
	ansible all -m systemd_service -a "name=iscsid enabled=yes state=started" -i ../ansible/host.ini --become
