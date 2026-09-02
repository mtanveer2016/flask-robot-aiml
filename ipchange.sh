#!/bin/bash
OLD_IP="10.226.22.234"
NEW_IP="10.226.22.234"
echo "Updating IP from $OLD_IP to $NEW_IP"
# Update kubeconfig
sudo sed -i "s/$OLD_IP/$NEW_IP/g" /etc/rancher/k3s/k3s.yaml
# Update Argo CD files
find ~/flask-robot-aiml/argocd -type f -name "*.yaml" -exec sed -i "s/$OLD_IP/$NEW_IP/g" {} \;
# Update Helm values
find ~/flask-robot-aiml/helm -type f -name "values*.yaml" -exec sed -i "s/$OLD_IP/$NEW_IP/g" {} \;
# Update any other config files
find ~/flask-robot-aiml -type f \( -name "*.yaml" -o -name "*.yml" -o -name "*.sh" \) -exec sed -i "s/$OLD_IP/$NEW_IP/g" {} \;
echo "Done! Please restart your services."


