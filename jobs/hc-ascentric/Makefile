REGISTRY ?= docker.home.dev

docker-build:
	docker build --platform linux/arm64 \
		-t ascentric:latest \
		-t $(REGISTRY)/ascentric:latest \
		.

docker-push:
	docker push $(REGISTRY)/ascentric:latest

install:
	helm upgrade --install hc-ascentric . -n ascentric --create-namespace

uninstall:
	helm uninstall hc-ascentric -n ascentric

# Build, push, install in one shot.
deploy: docker-build docker-push install

# Trigger an ad-hoc run of the CronJob (useful for smoke-testing).
run-now:
	kubectl create job -n ascentric --from=cronjob/ascentric-scraper ascentric-manual-$$(date +%s)
