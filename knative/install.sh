kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.16.1/serving-crds.yaml
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.16.1/serving-core.yaml
kubectl apply -f https://github.com/knative/net-kourier/releases/download/knative-v1.16.0/kourier.yaml
kubectl patch configmap/config-network \
  --namespace knative-serving \
  --type merge \
  --patch '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'
kubectl apply -f config-defaults.yaml
kubectl create secret generic custom-certs \
--namespace knative-serving \
--from-file=lab.cloud.crt
kubectl patch serviceaccount default -p "{\"imagePullSecrets\": [{\"name\": \"reg-cred\"}]}"


kubectl delete -f https://github.com/knative/net-kourier/releases/download/knative-v1.16.0/kourier.yaml
kubectl delete -f https://github.com/knative/serving/releases/download/knative-v1.16.1/serving-core.yaml
