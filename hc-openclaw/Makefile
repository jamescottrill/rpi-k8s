install:
	helm upgrade --install openclaw . -n openclaw --create-namespace
get-token:
	kubectl get openclawinstance openclaw -n openclaw -o jsonpath='{.status.gatewayToken}'
uninstall:
	helm uninstall openclaw -n openclaw
exec:
	kubectl exec -n openclaw pod/openclaw-0  -- $(filter-out $@,$(MAKECMDGOALS))
cp:
	kubectl cp $(word 2,$(MAKECMDGOALS)) openclaw/openclaw-0:$(word 3,$(MAKECMDGOALS))
%:
	@:



