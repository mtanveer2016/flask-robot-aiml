{{- define "flask-robot-aiml.fullname" -}}
{{- .Release.Name }}-{{ .Chart.Name }}
{{- end }}
