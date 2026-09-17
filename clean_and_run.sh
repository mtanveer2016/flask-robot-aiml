#!/bin/bash

echo "========================================="
echo "🧹 COMPLETE GPIO CLEANUP"
echo "========================================="

# 1. Stop K8s app completely
echo "1. Stopping K8s app..."
kubectl scale deployment flask-robot-aiml -n staging --replicas=0 2>/dev/null
#kubectl scale deployment flask-robot -n prod --replicas=0 2>/dev/null
#kubectl scale deployment robot-control -n default --replicas=0 2>/dev/null

# Wait for pods to terminate
sleep 3

# 2. Kill all Python processes
echo "2. Killing Python processes..."
sudo pkill -9 python 2>/dev/null
sudo pkill -9 python3 2>/dev/null
sudo killall python3 2>/dev/null
sudo killall python 2>/dev/null

# 3. Stop pigpio daemon if running
echo "3. Stopping pigpio..."
sudo systemctl stop pigpiod 2>/dev/null
sudo killall pigpiod 2>/dev/null

# 4. Free all GPIO pins
echo "4. Freeing GPIO pins..."
for pin in 4 5 6 12 13 16 17 18 19 20 21 22 23 24 25 26 27; do
    sudo sh -c "echo $pin > /sys/class/gpio/unexport" 2>/dev/null
done

# 5. Reset lgpio
echo "5. Resetting lgpio..."
sudo rm -rf /tmp/lgpio-socket-* 2>/dev/null

# 6. Check if any process is using /dev/mem
echo "6. Checking for processes using GPIO..."
sudo lsof /dev/mem 2>/dev/null | grep -v "lsof" || echo "   No processes found"

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "========================================="
echo "🚀 Starting your app..."
echo "========================================="
echo ""
echo "IMPORTANT: The K8s app is STOPPED."
echo "To restart K8s app later, run:"
echo "  kubectl scale deployment flask-robot-aiml -n staging --replicas=1"
echo ""

#cd /home/mtrobotcar/flask_robots_hw
#sudo python3 app.py

# restart grafana
 kubectl rollout restart deployment -n monitoring kube-prometheus-stack-grafana


# 7. Sync and restart
argocd app get flask-robot-aiml --hard-refresh
argocd app sync flask-robot-aiml
kubectl delete pod -n staging -l app=flask-robot-aiml


