from fastapi import FastAPI
from kubernetes import client, config
from kubernetes.client import V1PersistentVolumeClaim, V1PersistentVolumeClaimSpec, V1ResourceRequirements, V1StatefulSet, V1StatefulSetSpec, V1PodTemplateSpec, V1ObjectMeta, V1Container, V1ContainerPort, V1EnvVar, V1VolumeMount, V1Service, V1ServiceSpec, V1ServicePort

app = FastAPI()

try:
    config.load_incluster_config()
except config.config_exception.ConfigException:
    try:
        config.load_kube_config()
    except config.config_exception.ConfigException:
        raise Exception("Could not configure kubernetes python client")

@app.post("/deploy_stateful")
async def deploy_stateful(db_name: str):
    api_instance = client.AppsV1Api()
    core_api_instance = client.CoreV1Api()

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
        image="mysql:5.7",
        env=[
            V1EnvVar(name="MYSQL_ROOT_PASSWORD", value="password")
        ],
        ports=[client.V1ContainerPort(container_port=3306)],
        volume_mounts=[V1VolumeMount(name=f"{db_name}-pvc", mount_path="/var/lib/mysql")]
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
            ports=[V1ServicePort(port=3306, target_port=3306)]
        )
    )

    # Create the Service
    core_api_instance.create_namespaced_service(
        body=service,
        namespace="default"
    )

    return {"message": f"StatefulSet {db_name} and its service created"}