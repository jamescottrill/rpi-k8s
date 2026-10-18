# Re-vendor the upstream operator manifests: `make vendor VERSION=x.y.z`, then update appVersion in Chart.yaml.
VERSION ?= 26.8.1
BASE := https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/$(VERSION)/kubernetes
CRDS := keycloaks keycloakrealmimports keycloakoidcclients keycloaksamlclients

vendor:
	rm -f crds/*.yml templates/operator.yaml
	for c in $(CRDS); do curl -sfL -o crds/$$c.k8s.keycloak.org-v1.yml $(BASE)/$$c.k8s.keycloak.org-v1.yml; done
	# Keep the operator off the control-plane node, which has no spare memory, and give the JVM
	# up to ~5 minutes to start: the upstream 35s startup-probe budget is too short on a Pi.
	curl -sfL $(BASE)/kubernetes.yml \
		| yq 'select(.kind == "Deployment").spec.template.spec.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms = [{"matchExpressions": [{"key": "node-role.kubernetes.io/control-plane", "operator": "DoesNotExist"}]}]' \
		| yq 'select(.kind == "Deployment").spec.template.spec.containers[0].startupProbe.failureThreshold = 30' \
		> templates/operator.yaml
