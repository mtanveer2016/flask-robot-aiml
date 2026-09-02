#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Grafana on port 8080...${NC}"
kubectl port-forward -n monitoring svc/prometheus-grafana 8080:80 &
GRAFANA_PID=$!

echo -e "${GREEN}Starting Prometheus on port 9090...${NC}"
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 &
PROMETHEUS_PID=$!

echo -e "${GREEN}All services forwarded!${NC}"
echo -e "${YELLOW}Grafana: http://localhost:8080${NC}"
echo -e "${YELLOW}Prometheus: http://localhost:9090${NC}"
echo ""
echo "Press Ctrl+C to stop all port-forwards"

# Wait for user to press Ctrl+C
trap "echo -e '\n${GREEN}Stopping port-forwards...${NC}'; kill $GRAFANA_PID $PROMETHEUS_PID; exit 0" INT
wait
