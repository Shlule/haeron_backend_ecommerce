import secrets
import hashlib
import logging
from django.utils import timezone, timedelta
import strawberry
from strawberry.types import Info

from .models import ProvisioningAgent, AgentEnrollmentToken

from authUser.permission.permission import HasRole, IsAuthenticated

logger = logging.getLogger(__name__)

@strawberry.type
class CreateAgentResult:
    agent_id: int
    bootstrap_token: str

@strawberry.type
class UserMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated, HasRole("superadmin")])
    def create_provisioning_agent(self, info: Info, name: str, allowed_models: list[str]) -> CreateAgentResult:
        agent = ProvisioningAgent.objects.create(
            name=name,
            allowed_models=allowed_models,
            created_by=info.context["request"].user,
        )
        token = secrets.token_urlsafe(32)
        AgentEnrollmentToken.objects.create(
            agent=agent,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        logger.info("Agent %s créé par %s", agent.name, info.context["request"].user.username)
        return CreateAgentResult(agent_id=agent.id, bootstrap_token=token)
    
UserMutation = UserMutation