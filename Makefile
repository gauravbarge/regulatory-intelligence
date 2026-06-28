# Regulatory Intelligence Platform — Makefile
# Usage: make <target>

REGISTRY      ?= ghcr.io/gauravbarge/regulatory-intelligence
TAG           ?= latest
COMPOSE       := docker compose -f infra/docker-compose.yml
SERVICES      := supervisor research_agent developer_agent agile_master_agent document_analyst ingestion
K8S_NAMESPACE := regintel

.PHONY: help dev-up dev-up-agents dev-down build push test test-all k8s-apply k8s-delete lint fmt

help:
	@echo "Available targets:"
	@echo "  dev-up          Start infra services (Kafka, MongoDB, Qdrant, MinIO)"
	@echo "  dev-up-agents   Start infra + all Python agent services"
	@echo "  dev-down        Stop and remove all containers"
	@echo "  build           Build all Docker images"
	@echo "  push            Push images to $(REGISTRY)"
	@echo "  test            Run tests for all services (offline, no Docker needed)"
	@echo "  lint            Run ruff linter across all services"
	@echo "  fmt             Auto-format with ruff"
	@echo "  k8s-apply       Apply k8s manifests (requires kubectl context set)"
	@echo "  k8s-delete      Delete k8s namespace and all resources"

# ── Local dev ──────────────────────────────────────────────────────────────

dev-up:
	$(COMPOSE) up -d kafka mongodb qdrant minio kafka-init minio-init
	@echo "Infra ready. Run 'make dev-up-agents' to also start Python services."

dev-up-agents:
	$(COMPOSE) --profile agents up -d --build
	@echo "All services started. Logs: docker compose -f infra/docker-compose.yml logs -f"

dev-down:
	$(COMPOSE) --profile agents down -v
	@echo "All containers and volumes removed."

dev-logs:
	$(COMPOSE) --profile agents logs -f

# ── Build & push ───────────────────────────────────────────────────────────

build:
	@for svc in $(SERVICES); do \
		img_name=$$(echo $$svc | tr '_' '-'); \
		echo "Building $$img_name..."; \
		docker build \
			-f services/$$svc/Dockerfile \
			-t $(REGISTRY)/$$img_name:$(TAG) \
			.; \
	done

push: build
	@for svc in $(SERVICES); do \
		img_name=$$(echo $$svc | tr '_' '-'); \
		docker push $(REGISTRY)/$$img_name:$(TAG); \
	done

# ── Testing ────────────────────────────────────────────────────────────────

test:
	@echo "Running tests for medidata-common..."
	cd libs/common && python -m pytest -q
	@for svc in $(SERVICES); do \
		echo "Running tests for $$svc..."; \
		cd services/$$svc && python -m pytest -q && cd ../..; \
	done

test-common:
	cd libs/common && python -m pytest -v

test-supervisor:
	cd services/supervisor && python -m pytest -v

test-research:
	cd services/research_agent && python -m pytest -v

test-developer:
	cd services/developer_agent && python -m pytest -v

test-agile:
	cd services/agile_master_agent && python -m pytest -v

test-document:
	cd services/document_analyst && python -m pytest -v

test-ingestion:
	cd services/ingestion && python -m pytest -v

# ── Lint / format ──────────────────────────────────────────────────────────

lint:
	ruff check libs/ services/

fmt:
	ruff format libs/ services/
	ruff check --fix libs/ services/

# ── Kubernetes ─────────────────────────────────────────────────────────────

k8s-apply:
	kubectl apply -f infra/k8s/base/namespace.yaml
	kubectl apply -f infra/k8s/base/rbac.yaml
	kubectl apply -f infra/k8s/base/configmap.yaml
	@echo "Apply secrets manually: kubectl apply -f infra/k8s/base/secrets-template.yaml"
	kubectl apply -f infra/k8s/infra/
	kubectl apply -f infra/k8s/agents/
	@echo "Waiting for kafka-topic-init job..."
	kubectl wait --for=condition=complete job/kafka-topic-init -n $(K8S_NAMESPACE) --timeout=120s

k8s-status:
	kubectl get all -n $(K8S_NAMESPACE)

k8s-delete:
	kubectl delete namespace $(K8S_NAMESPACE) --ignore-not-found
