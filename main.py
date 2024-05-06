from fastapi import FastAPI
from kubernetes import client, config
from kubernetes.client import V1PersistentVolumeClaim, V1PersistentVolumeClaimSpec, V1ResourceRequirements, V1StatefulSet, V1StatefulSetSpec, V1PodTemplateSpec, V1ObjectMeta, V1Container, V1ContainerPort, V1EnvVar, V1VolumeMount, V1Service, V1ServiceSpec, V1ServicePort
from enum import Enum
from typing import Dict, List

app = FastAPI()

class DatabaseType(str, Enum):
    mongodb = "mongodb"
    mysql = "mysql"
    postgresql = "postgresql"
    redis = "redis"

# Database configurations
database_configs: Dict[str, Dict] = {
    "mongodb": {
        "image": "mongo:latest",
        "env": [
            V1EnvVar(name="MONGO_INITDB_ROOT_USERNAME", value="root"),
            V1EnvVar(name="MONGO_INITDB_ROOT_PASSWORD", value="password"),
            V1EnvVar(name="MONGO_INITDB_DATABASE", value="datzen")
        ],
        "ports": [V1ContainerPort(container_port=27017)],
        "volume_mount_path": "/data/db"
    },
    "mysql": {
        "image": "mysql:latest",
        "env": [
            V1EnvVar(name="MYSQL_ROOT_PASSWORD", value="password"),
            V1EnvVar(name="MYSQL_DATABASE", value="datzen")
        ],
        "ports": [V1ContainerPort(container_port=3306)],
        "volume_mount_path": "/var/lib/mysql"
    },
    "postgresql": {
        "image": "postgres:latest",
        "env": [
            V1EnvVar(name="POSTGRES_USER", value="postgres"),
            V1EnvVar(name="POSTGRES_PASSWORD", value="password"),
            V1EnvVar(name="POSTGRES_DB", value="datzen")
        ],
        "ports": [V1ContainerPort(container_port=5432)],
        "volume_mount_path": "/var/lib/postgresql/data"
    },
    "redis": {
        "image": "redis:latest",
        "env": [
            V1EnvVar(name="REDIS_USERNAME", value="user"),
            V1EnvVar(name="REDIS_PASSWORD", value="password")
        ],
        "ports": [V1ContainerPort(container_port=6379)],
        "volume_mount_path": "/data"
    }
}

try:
    config.load_incluster_config()
except config.config_exception.ConfigException:
    try:
        config.load_kube_config()
    except config.config_exception.ConfigException:
        raise Exception("Could not configure kubernetes python client")

@app.post("/deploydb/{db_type}")
async def deploydb(db_name: str, db_type: DatabaseType):
    api_instance = client.AppsV1Api()
    core_api_instance = client.CoreV1Api()

    if db_type not in database_configs:
        raise ValueError(f"Unsupported database type: {db_type}")

    db_config = database_configs[db_type]

    # Define the volume claim template
    volume_claim_template = V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name=f"{db_name}-pvc"),
        spec=V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=V1ResourceRequirements(
                requests={"storage": "1Gi"}
            )
        )
    )

    # Define the container
    container = client.V1Container(
        name=db_name,
        image=db_config["image"],
        env=db_config["env"],
        ports=db_config["ports"],
        volume_mounts=[V1VolumeMount(name=f"{db_name}-pvc", mount_path=db_config["volume_mount_path"])]
    )

    # Define the pod spec
    pod_spec = client.V1PodSpec(
        containers=[container]
    )

    # Define the StatefulSet spec
    stateful_set_spec = V1StatefulSetSpec(
        service_name=db_name,  
        replicas=1,
        selector=client.V1LabelSelector(
            match_labels={"app": db_name}
        ),
        template=V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": db_name}),
            spec=pod_spec
        ),
        volume_claim_templates=[volume_claim_template]
    )

    # Define the StatefulSet
    stateful_set = V1StatefulSet(
        api_version="apps/v1",
        kind="StatefulSet",
        metadata=client.V1ObjectMeta(name=db_name),
        spec=stateful_set_spec
    )

    # Create the StatefulSet
    api_instance.create_namespaced_stateful_set(
        body=stateful_set,
        namespace="default"
    )

    # Define the Service
    service = V1Service(
        api_version="v1",
        kind="Service",
        metadata=V1ObjectMeta(name=f"{db_name}-service"),
        spec=V1ServiceSpec(
            type="NodePort",
            selector={"app": db_name},
            ports=[V1ServicePort(port=db_config["ports"][0].container_port, target_port=db_config["ports"][0].container_port)]
        )
    )

    # Create the Service
    core_api_instance.create_namespaced_service(
        body=service,
        namespace="default"
    )

    return {"message": f"StatefulSet {db_name} and its service for {db_type} created"}
