"""Restore SPA/landing release archives when ECS metric rollback fires.

Triggered by EventBridge on ``ECS Deployment State Change`` /
``SERVICE_DEPLOYMENT_FAILED`` (circuit breaker or CloudWatch deploy alarms),
or by a sustained UnHealthyHostCount alarm after deploy.

ECS may already have rolled the API task definition back; this Lambda
re-pins services to the previous ECR SHA, restores S3 releases, and notifies SNS.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import boto3
from botocore.exceptions import ClientError

ssm = boto3.client("ssm")
s3 = boto3.client("s3")
cloudfront = boto3.client("cloudfront")
sns = boto3.client("sns")
ecs = boto3.client("ecs")


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required env var {name}")
    return value


def _param(name: str) -> str:
    return ssm.get_parameter(Name=name)["Parameter"]["Value"].strip()


def _put_param(name: str, value: str) -> None:
    ssm.put_parameter(Name=name, Value=value, Type="String", Overwrite=True)


def _s3_release_exists(bucket: str, sha: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=f"releases/{sha}/index.html")
        return True
    except ClientError:
        return False


def _restore_bucket(bucket: str, sha: str, dist_id: str) -> None:
    prefix = f"releases/{sha}/"
    paginator = s3.get_paginator("list_objects_v2")
    release_keys: set[str] = set()
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            relative = key[len(prefix) :]
            if not relative or relative.endswith("/"):
                continue
            release_keys.add(relative)
            s3.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": key},
                Key=relative,
            )

    # Delete live objects that are not in the release (preserve releases/).
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.startswith("releases/"):
                continue
            if key not in release_keys:
                s3.delete_object(Bucket=bucket, Key=key)

    cloudfront.create_invalidation(
        DistributionId=dist_id,
        InvalidationBatch={
            "Paths": {"Quantity": 1, "Items": ["/*"]},
            "CallerReference": f"metric-rollback-{sha}-{dist_id}",
        },
    )


def _roll_service_to_image(cluster: str, service: str, image: str) -> None:
    described = ecs.describe_task_definition(taskDefinition=service)
    td = described["taskDefinition"]
    for key in (
        "taskDefinitionArn",
        "revision",
        "status",
        "requiresAttributes",
        "compatibilities",
        "registeredAt",
        "registeredBy",
    ):
        td.pop(key, None)

    for container in td.get("containerDefinitions", []):
        container["image"] = image
        for env in container.get("environment") or []:
            if env.get("name") == "DAGSTER_CURRENT_IMAGE":
                env["value"] = image

    registered = ecs.register_task_definition(**td)
    new_arn = registered["taskDefinition"]["taskDefinitionArn"]
    ecs.update_service(cluster=cluster, service=service, taskDefinition=new_arn)


def _notify(topic: str, subject: str, message: dict[str, Any]) -> None:
    sns.publish(TopicArn=topic, Subject=subject[:100], Message=json.dumps(message, indent=2))


def _health_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError):
        return False


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    previous_param = _env("PREVIOUS_SHA_PARAM")
    current_param = _env("CURRENT_SHA_PARAM")
    topic = _env("SNS_TOPIC_ARN")
    cluster = _env("ECS_CLUSTER")
    api_service = _env("API_SERVICE")
    ecr_url = _env("ECR_REPOSITORY_URL")
    frontend_bucket = _env("FRONTEND_BUCKET")
    frontend_dist = _env("FRONTEND_DISTRIBUTION_ID")
    landing_bucket = _env("LANDING_BUCKET")
    landing_dist = _env("LANDING_DISTRIBUTION_ID")
    health_url = os.environ.get("API_HEALTH_URL", "").strip()

    previous = _param(previous_param)
    current = _param(current_param)

    detail = event.get("detail") or {}
    reason = {
        "trigger": event.get("detail-type") or event.get("source") or "unknown",
        "eventName": detail.get("eventName"),
        "deploymentId": detail.get("deploymentId"),
        "reason": detail.get("reason"),
        "alarmName": detail.get("alarmName"),
        "previous_sha": previous,
        "current_sha": current,
    }

    # Idempotent: if we already live on the previous SHA, just notify.
    if current == previous and previous not in ("", "none"):
        _notify(topic, "ECS metric rollback no-op (already on previous SHA)", reason)
        return {"ok": True, "skipped": True, **reason}

    if not previous or previous == "none":
        _notify(topic, "ECS metric rollback skipped (no previous SHA)", reason)
        return {"ok": False, "reason": "no_previous_sha", **reason}

    image = f"{ecr_url}:{previous}"
    services = [api_service]
    ingestion = os.environ.get("INGESTION_SERVICE", "").strip()
    dask = os.environ.get("DASK_WORKER_SERVICE", "").strip()
    if ingestion:
        services.append(ingestion)
    if dask:
        services.append(dask)

    for service in services:
        _roll_service_to_image(cluster, service, image)

    restored = {"frontend": False, "landing": False}
    if _s3_release_exists(frontend_bucket, previous):
        _restore_bucket(frontend_bucket, previous, frontend_dist)
        restored["frontend"] = True
    if _s3_release_exists(landing_bucket, previous):
        _restore_bucket(landing_bucket, previous, landing_dist)
        restored["landing"] = True

    # After a successful metric rollback, the previous SHA is live again.
    _put_param(current_param, previous)

    health = None
    if health_url:
        health = _health_ok(health_url)

    result = {
        "ok": True,
        "rolled_back_to": previous,
        "image": image,
        "services": services,
        "restored": restored,
        "health_ok": health,
        **reason,
    }
    _notify(topic, f"ECS metric rollback → {previous[:12]}", result)
    return result
