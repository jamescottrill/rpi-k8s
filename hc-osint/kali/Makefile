docker-build:
	docker build . -t docker.home.internal/kali:latest
docker-push:
	docker push docker.home.internal/kali:latest
install:
	helm upgrade --install hc-kali helm-charts -n kali --create-namespace