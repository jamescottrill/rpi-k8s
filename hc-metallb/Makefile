install:
	helm upgrade --install metallb . -n metallb --create-namespace
uninstall:
	helm uninstall metallb -n metallb
charts:
	kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.15.3/config/manifests/metallb-native.yaml