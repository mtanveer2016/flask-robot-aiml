#!/bin/bash

echo "🔍 Starting monitoring fix script..."

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# === 1. Check if staging namespace exists ===
echo -e "\n${YELLOW}[1/8] Checking staging namespace...${NC}"
if ! kubectl get namespace staging &> /dev/null; then
    echo "Creating staging namespace..."
    kubectl create namespace staging
else
    echo "✅ Staging namespace exists"
fi

# === 2. Check if pod is running ===
echo -e "\n${YELLOW}[2/8] Checking Flask pod...${NC}"
POD_NAME=$(kubectl get pods -n staging -l app=flask-robot -o jsonpath="{.items[0].metadata.name}" 2>/dev/null)
if [ -z "$POD_NAME" ]; then
    echo "❌ No Flask pod found! Please deploy your application first."
    exit 1
else
    echo "✅ Flask pod running: $POD_NAME"
fi

# === 3. Check service labels ===
echo -e "\n${YELLOW}[3/8] Checking service labels...${NC}"
kubectl label svc -n staging flask-robot app=flask-robot --overwrite &> /dev/null
kubectl label svc -n staging flask-robot release=prometheus --overwrite &> /dev/null
echo "✅ Service labels updated"

# === 4. Ensure service has a named port ===
echo -e "\n${YELLOW}[4/8] Checking service port name...${NC}"
PORT_NAME=$(kubectl get svc -n staging flask-robot -o jsonpath="{.spec.ports[0].name}" 2>/dev/null)
if [ -z "$PORT_NAME" ] || [ "$PORT_NAME" != "http" ]; then
    echo "Adding port name 'http'..."
    kubectl patch svc -n staging flask-robot --type='json' -p='[{"op": "add", "path": "/spec/ports/0/name", "value": "http"}]' &> /dev/null || echo "Port name already exists or could not be added"
else
    echo "✅ Service has port name: $PORT_NAME"
fi

# === 5. Apply the correct ServiceMonitor ===
echo -e "\n${YELLOW}[5/8] Applying ServiceMonitor...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: flask-robot-monitor
  namespace: monitoring
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: flask-robot
  namespaceSelector:
    matchNames:
      - staging
  endpoints:
    - port: http
      interval: 30s
      path: /metrics
EOF
echo "✅ ServiceMonitor applied"

# === 6. Verify ServiceMonitor ===
echo -e "\n${YELLOW}[6/8] Verifying ServiceMonitor...${NC}"
NAMESPACE=$(kubectl get servicemonitor -n monitoring flask-robot-monitor -o jsonpath="{.spec.namespaceSelector.matchNames[0]}" 2>/dev/null)
if [ "$NAMESPACE" = "staging" ]; then
    echo "✅ ServiceMonitor correctly configured for 'staging' namespace"
else
    echo "❌ ServiceMonitor still pointing to wrong namespace: $NAMESPACE"
    echo "Applying fix again..."
    kubectl patch servicemonitor -n monitoring flask-robot-monitor --type='json' -p='[{"op": "replace", "path": "/spec/namespaceSelector/matchNames", "value": ["staging"]}]' &> /dev/null
    echo "✅ ServiceMonitor patched"
fi

# === 7. Force Prometheus reload ===
echo -e "\n${YELLOW}[7/8] Reloading Prometheus...${NC}"
NODEPORT=$(kubectl get svc -n monitoring prometheus-kube-prometheus-prometheus -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)
if [ -n "$NODEPORT" ]; then
    curl -X POST "http://10.103.216.235:$NODEPORT/-/reload" 2>/dev/null && echo "✅ Prometheus reloaded"
else
    echo "⚠️ Could not find Prometheus NodePort, skipping reload"
fi

# === 8. Test metrics ===
echo -e "\n${YELLOW}[8/8] Testing metrics...${NC}"
sleep 5  # Wait for reload

RESULT=$(curl -G -s "http://10.103.216.235:$NODEPORT/api/v1/query" \
  --data-urlencode 'query=robot_battery_voltage{namespace="staging"}' 2>/dev/null | jq -r '.data.result[0].value[1]' 2>/dev/null)

if [ -n "$RESULT" ] && [ "$RESULT" != "null" ]; then
    echo -e "${GREEN}✅ Metrics working! Battery voltage: $RESULT V${NC}"
else
    echo -e "${RED}❌ Still no metrics. Waiting 30 seconds for Prometheus to scrape...${NC}"
    sleep 30
    RESULT=$(curl -G -s "http://10.103.216.235:$NODEPORT/api/v1/query" \
      --data-urlencode 'query=robot_battery_voltage{namespace="staging"}' 2>/dev/null | jq -r '.data.result[0].value[1]' 2>/dev/null)
    if [ -n "$RESULT" ] && [ "$RESULT" != "null" ]; then
        echo -e "${GREEN}✅ Metrics now working! Battery voltage: $RESULT V${NC}"
    else
        echo -e "${RED}❌ Metrics still not available. Please check Prometheus targets at: http://10.103.216.235:$NODEPORT/targets${NC}"
    fi
fi

echo -e "\n${GREEN}✅ Fix script completed!${NC}"
echo ""
echo "📊 Access services at:"
echo "  - Prometheus: http://10.103.216.235:$NODEPORT"
echo "  - Targets:    http://10.103.216.235:$NODEPORT/targets"
echo ""
echo "🔍 To test queries manually:"
echo "  curl -G -s 'http://10.103.216.235:$NODEPORT/api/v1/query' --data-urlencode 'query=robot_battery_voltage{namespace=\"staging\"}' | jq ."

