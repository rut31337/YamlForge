from typing import Dict, List, Optional
from pydantic import BaseModel


class ProviderConfig(BaseModel):
    name: str
    display_name: str
    enabled: bool = True
    supports_gpu: bool = False
    supports_openshift: bool = False
    regions: List[str] = []


class AppConfig(BaseModel):
    app_title: str = "DemoBuilder - Infrastructure Assistant"
    max_conversation_turns: int = 50
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    redis_enabled: bool = False
    redis_url: Optional[str] = None
    keycloak_enabled: bool = False
    
    providers: Dict[str, ProviderConfig] = {
        "aws": ProviderConfig(
            name="aws",
            display_name="Amazon Web Services (AWS)",
            enabled=True,
            supports_gpu=True,
            supports_openshift=True,
            regions=["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
        ),
        "azure": ProviderConfig(
            name="azure",
            display_name="Microsoft Azure",
            enabled=True,
            supports_gpu=True,
            supports_openshift=True,
            regions=["eastus", "westus2", "northeurope", "southeastasia"]
        ),
        "gcp": ProviderConfig(
            name="gcp",
            display_name="Google Cloud Platform (GCP)",
            enabled=True,
            supports_gpu=True,
            supports_openshift=False,
            regions=["us-central1", "us-west1", "europe-west1", "asia-southeast1"]
        ),
        "ibm_vpc": ProviderConfig(
            name="ibm_vpc",
            display_name="IBM Cloud VPC",
            enabled=True,
            supports_gpu=False,
            supports_openshift=False,
            regions=["us-south", "us-east", "eu-gb", "eu-de"]
        ),
        "ibm_classic": ProviderConfig(
            name="ibm_classic",
            display_name="IBM Cloud Classic",
            enabled=True,
            supports_gpu=False,
            supports_openshift=False,
            regions=["dal10", "dal12", "wdc07", "lon06"]
        ),
        "cnv": ProviderConfig(
            name="cnv",
            display_name="Container Native Virtualization (CNV)",
            enabled=True,
            supports_gpu=True,
            supports_openshift=True,
            regions=["cluster-default"]
        ),
        "oci": ProviderConfig(
            name="oci",
            display_name="Oracle Cloud Infrastructure (OCI)",
            enabled=False,
            supports_gpu=True,
            supports_openshift=False,
            regions=["us-ashburn-1", "us-phoenix-1", "eu-frankfurt-1", "ap-tokyo-1"]
        ),
        "alibaba": ProviderConfig(
            name="alibaba",
            display_name="Alibaba Cloud",
            enabled=False,
            supports_gpu=True,
            supports_openshift=False,
            regions=["us-east-1", "us-west-1", "eu-central-1", "ap-southeast-1"]
        ),
        "vmware": ProviderConfig(
            name="vmware",
            display_name="VMware vSphere",
            enabled=False,
            supports_gpu=False,
            supports_openshift=False,
            regions=["datacenter-1", "datacenter-2"]
        ),
        "cheapest-gpu": ProviderConfig(
            name="cheapest-gpu",
            display_name="Cost Optimized GPU",
            enabled=False,
            supports_gpu=True,
            supports_openshift=False,
            regions=["auto-select"]
        )
    }


def get_app_config() -> AppConfig:
    return AppConfig()


def get_enabled_providers(config: AppConfig) -> List[str]:
    return [
        provider_name for provider_name, provider_config in config.providers.items()
        if provider_config.enabled
    ]


def get_gpu_providers(config: AppConfig) -> List[str]:
    return [
        provider_name for provider_name, provider_config in config.providers.items()
        if provider_config.enabled and provider_config.supports_gpu
    ]


def get_openshift_providers(config: AppConfig) -> List[str]:
    return [
        provider_name for provider_name, provider_config in config.providers.items()
        if provider_config.enabled and provider_config.supports_openshift
    ]
