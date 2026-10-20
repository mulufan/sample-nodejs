#!/usr/bin/env python3
"""Minimal Kubernetes monitor that exports Prometheus metrics.

Every 15 seconds it lists nodes, pods and deployments through the existing
kubeconfig (docker-desktop context) and serves cluster-wide totals on
localhost:8002/metrics. It only makes read-only list calls.

CPU and memory usage need Metrics Server and are planned as a later step.

Setup: python -m venv monitoring/.venv
       monitoring/.venv/Scripts/python -m pip install -r monitoring/requirements.txt
Usage: monitoring/.venv/Scripts/python monitoring/k8s_monitor.py
"""
import logging
import time

from kubernetes import client, config
from prometheus_client import Gauge, start_http_server

CONTEXT = "docker-desktop"
PORT = 8002
INTERVAL = 15  # seconds between collections
TIMEOUT = 10  # seconds per API call, so a hung API server cannot stall the loop

NODES_READY = Gauge("k8s_nodes_ready", "Nodes whose Ready condition is True")
NODES_NOT_READY = Gauge("k8s_nodes_not_ready", "Nodes whose Ready condition is not True")
PODS_RUNNING = Gauge("k8s_pods_running", "Pods in the Running phase")
PODS_FAILED = Gauge("k8s_pods_failed", "Pods in the Failed phase")
PODS_TOTAL = Gauge("k8s_pods_total", "Pods in all namespaces")
POD_RESTARTS = Gauge("k8s_pod_restarts", "Container restarts summed over all pods")
DEPLOYMENTS_UNAVAILABLE = Gauge(
    "k8s_deployments_unavailable", "Deployments with fewer available replicas than desired"
)
SUCCESS = Gauge("k8s_monitor_success", "1 if the last collection succeeded, 0 if it failed")
CLUSTER_GAUGES = (
    NODES_READY, NODES_NOT_READY, PODS_RUNNING, PODS_FAILED, PODS_TOTAL, POD_RESTARTS, DEPLOYMENTS_UNAVAILABLE
)


def node_is_ready(node):
    return any(c.type == "Ready" and c.status == "True" for c in node.status.conditions or [])


def collect():
    # Reload the kubeconfig each cycle: Docker Desktop can change the API port on restart
    with config.new_client_from_config(context=CONTEXT) as api:
        core, apps = client.CoreV1Api(api), client.AppsV1Api(api)
        nodes = core.list_node(_request_timeout=TIMEOUT).items
        pods = core.list_pod_for_all_namespaces(_request_timeout=TIMEOUT).items
        deployments = apps.list_deployment_for_all_namespaces(_request_timeout=TIMEOUT).items

    ready = sum(node_is_ready(n) for n in nodes)
    NODES_READY.set(ready)
    NODES_NOT_READY.set(len(nodes) - ready)
    PODS_RUNNING.set(sum(p.status.phase == "Running" for p in pods))
    PODS_FAILED.set(sum(p.status.phase == "Failed" for p in pods))
    PODS_TOTAL.set(len(pods))
    POD_RESTARTS.set(sum(c.restart_count for p in pods for c in p.status.container_statuses or []))
    # status.available_replicas is omitted by the API when it is 0
    DEPLOYMENTS_UNAVAILABLE.set(
        sum((d.status.available_replicas or 0) < (d.spec.replicas or 0) for d in deployments)
    )


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start_http_server(PORT, addr="127.0.0.1")  # serves /metrics from a background thread
    logging.info("serving http://127.0.0.1:%d/metrics (context %s)", PORT, CONTEXT)
    while True:
        try:
            collect()
            SUCCESS.set(1)
        except Exception as error:  # keep running; the failure shows up as k8s_monitor_success 0
            # NaN instead of the last values, so a failed collection never looks healthy
            for gauge in CLUSTER_GAUGES:
                gauge.set(float("nan"))
            SUCCESS.set(0)
            # Type and HTTP status only: API error bodies and headers are not logged
            logging.warning("collection failed: %s %s", type(error).__name__, getattr(error, "status", ""))
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
