from rest_framework.permissions import BasePermission
 
from .models import AgentType
 
 
def agent_type_permission(required_type: AgentType):
    """
    Factory de permission DRF : n'autorise que les agents dont agent_type
    correspond exactement à required_type.
 
    Nécessite AgentTokenAuthentication en amont (request.user = ProvisionningAgent).
 
    Usage:
        permission_classes = [agent_type_permission(AgentType.ENGRAVING)]
    """
 
    class _AgentTypePermission(BasePermission):
        message = f"Cet agent n'est pas autorisé à utiliser cette route (type requis: {required_type})."
 
        def has_permission(self, request, view):
            agent = getattr(request, "user", None)
            return getattr(agent, "agent_type", None) == required_type
 
    return _AgentTypePermission
