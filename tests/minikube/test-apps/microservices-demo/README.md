# Microservices Demo for CNI Migration Testing

This directory contains a simple microservices application for testing CNI migration. The application consists of three services:

1. **Frontend**: Serves as the entry point and forwards requests to the backend
2. **Backend**: Processes requests and communicates with the database
3. **Database**: Stores and retrieves data

## Architecture

```
[Frontend] --> [Backend] --> [Database]
```

## Network Policies

The application includes network policies that enforce the following rules:

- Frontend can only communicate with Backend
- Backend can only communicate with Database
- Database only accepts connections from Backend
- All services can communicate with DNS (kube-dns)

## Deployment

To deploy the application:

```bash
kubectl apply -f namespace.yaml
kubectl apply -f database.yaml
kubectl apply -f backend.yaml
kubectl apply -f frontend.yaml
kubectl apply -f network-policies.yaml
```

## Testing

To test the application:

```bash
# Get the frontend pod name
FRONTEND_POD=$(kubectl get pod -n microservices -l app=frontend -o jsonpath='{.items[0].metadata.name}')

# Test frontend service
kubectl exec -n microservices $FRONTEND_POD -- curl -s http://frontend:80

# Test backend service via frontend
kubectl exec -n microservices $FRONTEND_POD -- curl -s http://frontend:80/api

# Test database service via frontend and backend
kubectl exec -n microservices $FRONTEND_POD -- curl -s http://frontend:80/api/db
```

## Expected Results

- Frontend service should return "Frontend Service"
- Backend service should return "Backend Service"
- Database service should return "Database Service"
