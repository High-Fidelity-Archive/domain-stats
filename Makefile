.PHONY: docker
docker:
	docker build -t highfidelity/domain-stats:latest .
	docker push highfidelity/domain-stats:latest
