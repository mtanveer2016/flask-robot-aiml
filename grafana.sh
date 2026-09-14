#!/bin/bash
echo "🔧 Fixing Grafana Data Source"

# 1. Find the correct Prometheus service name
PROM_SVC=$(kubectl get svc -n monitoring -o name | grep prometheus | head -1)
echo "✅ Prometheus service: $PROM_SVC"

# 2. Check if Grafana data source is configured correctly
echo "📊 Checking Grafana data source..."
kubectl get configmap -n monitoring -o name | grep grafana | grep datasource

# 3. Restart Grafana to refresh connections
echo "🔄 Restarting Grafana..."
kubectl rollout restart deployment -n monitoring kube-prometheus-stack-grafana

# 4. Wait for Grafana to be ready
echo "⏳ Waiting for Grafana to be ready..."
kubectl wait --for=condition=ready pod -n monitoring -l app.kubernetes.io/name=grafana --timeout=120s

echo -e "\n✅ Fix applied!"
echo "📊 Access Grafana: http://10.226.22.234:30272"
echo "📊 Login: admin / prom-operator"
echo "📊 Go to Configuration → Data Sources → Prometheus"
echo "📊 URL should be: http://prometheus-operated:9090"
