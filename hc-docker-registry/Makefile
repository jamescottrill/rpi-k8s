install:
	helm upgrade --install docker-registry . -n docker-registry --create-namespace

uninstall:
	helm uninstall docker-registry -n docker-registry
secret:
	kubectl create secret docker-registry regcred --docker-server=docker.home.internal --docker-username=a5QxbI0ZmTh --docker-password=b2ojjtF%7rKHJcpI