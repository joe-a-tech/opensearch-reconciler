from .component_templates import ComponentTemplateReconciler
from .index_templates import IndexTemplateReconciler
from .ingest_pipelines import IngestPipelineReconciler
from .ism_policies import ISMPolicyReconciler
from .role_mappings import RoleMappingReconciler
from .roles import RoleReconciler
from .tenant import TenantReconciler
from .users import UserReconciler

RECONCILERS = {
    "tenant": TenantReconciler(),
    "roles": RoleReconciler(),
    "role_mappings": RoleMappingReconciler(),
    "users": UserReconciler(),
    "index_templates": IndexTemplateReconciler(),
    "component_templates": ComponentTemplateReconciler(),
    "ingest_pipelines": IngestPipelineReconciler(),
    "ism_policies": ISMPolicyReconciler(),
}