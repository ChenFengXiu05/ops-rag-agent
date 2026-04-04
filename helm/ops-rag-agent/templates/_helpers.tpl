{{/*
Expand the name of the chart.
*/}}
{{- define "ops-rag-agent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ops-rag-agent.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "ops-rag-agent.labels" -}}
helm.sh/chart: {{ include "ops-rag-agent.name" . }}-{{ .Chart.Version }}
{{ include "ops-rag-agent.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "ops-rag-agent.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ops-rag-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
