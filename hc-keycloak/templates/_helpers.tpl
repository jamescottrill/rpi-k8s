{{/* Environment variable holding a client's secret, e.g. oauth2-proxy -> CLIENT_SECRET_OAUTH2_PROXY. */}}
{{- define "hc-keycloak.clientSecretEnv" -}}
CLIENT_SECRET_{{ . | upper | replace "-" "_" }}
{{- end -}}
