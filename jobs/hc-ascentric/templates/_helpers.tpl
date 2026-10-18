{{/* Common labels applied to every resource rendered by hc-ascentric. */}}
{{- define "hc-ascentric.labels" -}}
app.kubernetes.io/name: hc-ascentric
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}
