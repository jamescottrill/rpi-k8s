# Argo CD (ApplicationSet `cluster`) manages this release; these targets are
# only for bootstrapping a fresh cluster, before Argo CD is installed.
#
# Migrating from kube-system: let Argo CD do it. It creates everything in the
# traefik namespace and prunes the kube-system copies. Expect a brief outage
# while the LoadBalancer IP moves to the new Service. Do NOT `helm uninstall
# -n kube-system` first: that deletes the live Traefik before its replacement
# exists. Once Argo has synced, drop the stale Helm release records left from
# the original manual install:
#   kubectl delete secret -n kube-system -l owner=helm,name=hc-traefik
install:
	helm upgrade --install hc-traefik . -n traefik --create-namespace
uninstall:
	helm uninstall hc-traefik -n traefik

