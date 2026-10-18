{{/* Space-separated client IDs, for the keycloak-config hook. */}}
{{- define "hc-keycloak.clientNames" -}}
{{- $names := list -}}
{{- range .Values.clients }}{{ $names = append $names .name }}{{ end -}}
{{- join " " $names -}}
{{- end -}}
