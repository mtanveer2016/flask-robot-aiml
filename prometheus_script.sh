#!/bin/bash
echo "🔧 Fixing ServiceMonitor for NodePort Prometheus"

# 1. Add the label that the NodePort Prometheus expects
echo "📝 Adding release=kube-prometheus-stack label..."
kubectl label servicemonitor -n monitoring flask-robot-monitor release=kube-prometheus-stack --overwrite

# 2. Check the ServiceMonitor labels
echo "📊 ServiceMonitor labels:"
kubectl get servicemonitor -n monitoring flask-robot-monitor --show-labels

# 3. Reload Prometheus
echo "🔄 Reloading Prometheus..."
curl -X POST "http://10.70.133.234:31691/-/reload" 2>/dev/null && echo "✅ Reloaded" || echo "⚠️ Auto-reload in 30s"

# 4. Wait and check targets
echo "⏳ Waiting 15 seconds for Prometheus to refresh..."
sleep 15

echo "📊 Checking targets..."
curl -s "http://10.70.133.234:31691/api/v1/targets" | python3 -c "
import sys, json
data = json.load(sys.stdin)
targets = data.get('data', {}).get('activeTargets', [])
staging_targets = [t for t in targets if t.get('labels', {}).get('namespace') == 'staging']
if staging_targets:
    print('✅ Found staging targets:')
    for t in staging_targets:
        print(f'  - {t.get(\"scrapeUrl\")} - State: {t.get(\"health\")}')
else:
    print('❌ No staging targets found')
    namespaces = set([t.get('labels', {}).get('namespace') for t in targets if t.get('labels', {}).get('namespace')])
    print(f'Namespaces with targets: {namespaces}')
"

echo -e "\n📊 Check query: http://10.70.133.234:31691/graph?g0.expr=robot_battery_voltage%7Bnamespace%3D%22staging%22%7D"
