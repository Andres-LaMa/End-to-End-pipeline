.PHONY: help build up down logs tui load deploy redeploy k8s-status

IMAGE := todo-app:local
NAMESPACE := default

help:
	@echo "make build      - собрать образ"
	@echo "make up         - поднять API через compose"
	@echo "make down       - остановить compose"
	@echo "make tui        - запустить TUI"
	@echo "make load       - загрузить образ в minikube"
	@echo "make deploy     - применить k8s-манифесты"
	@echo "make redeploy   - пересобрать + load + rollout restart"
	@echo "make k8s-status - статус подов, сервисов, PVC"

build:
	docker compose build

up:
	docker compose up -d api

down:
	docker compose down

logs:
	docker compose logs -f api

tui:
	docker compose --profile tui run --rm tui

load:
	minikube image load $(IMAGE)

deploy:
	kubectl apply -f k8s/

redeploy: build load
	kubectl rollout restart deployment/todo-api
	kubectl rollout status deployment/todo-api

k8s-status:
	kubectl get pods,svc,pvc
