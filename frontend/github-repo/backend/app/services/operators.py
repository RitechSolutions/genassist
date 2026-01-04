from datetime import datetime, timezone
from uuid import UUID
from fastapi import Depends
from fastapi_injector import Injected
from injector import inject

from app.auth.utils import generate_unique_username, get_password_hash
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models import OperatorModel, OperatorStatisticsModel, UserModel, UserRoleModel
from app.repositories.conversations import ConversationRepository
from app.repositories.operators import OperatorRepository
from app.repositories.roles import RolesRepository
from app.repositories.user_types import UserTypesRepository
from app.repositories.users import UserRepository
from app.schemas.operator import OperatorCreate, OperatorRead


@inject
class OperatorService:

    def __init__(self,
                 operator_repository: OperatorRepository,
                 user_repository: UserRepository,
                 user_types_repository: UserTypesRepository,
                 roles_repository: RolesRepository,
                 conversation_repository: ConversationRepository
                 ):  # Auto-inject repository
        self.operator_repo = operator_repository
        self.conversation_repo = conversation_repository
        self.user_repository = user_repository
        self.user_types_repository = user_types_repository
        self.roles_repository = roles_repository

    # ----------  helpers  ------------------------------------------------

    async def create(self, operator_create: OperatorCreate, generated_password):
        if await self.user_repository.get_by_email(operator_create.user.email):
            raise AppException(error_key=ErrorKey.EMAIL_ALREADY_EXISTS)

        # --- 1) build UserModel -----------------------------------------
        user_type = await self.user_types_repository.get_by_name("interactive")
        new_user = UserModel(
                username= await generate_unique_username(self.user_repository, operator_create.first_name,
                                                         operator_create.last_name),
                hashed_password=get_password_hash(generated_password),
                email=operator_create.user.email,
                is_active=1,
                user_type_id=user_type.id,
                force_upd_pass_date=datetime.now(timezone.utc),
                )

        operator_role = await self.roles_repository.get_by_name("operator")
        if operator_role is None or not operator_role.is_active:
            raise AppException(error_key=ErrorKey.OPERATOR_ROLE_MISSING)

        # Association-object pattern ⇒ push a UserRoleModel instance
        new_user.user_roles.append(UserRoleModel(role=operator_role))

        # --- 2) build OperatorStatisticsModel ---------------------------
        stats = OperatorStatisticsModel(**operator_create.operator_statistics.model_dump())

        # --- 3) build OperatorModel & wire it up ------------------------
        new_operator = OperatorModel(
                first_name=operator_create.first_name,
                last_name=operator_create.last_name,
                avatar=operator_create.avatar,
                is_active=1,
                operator_statistics=stats,
                user=new_user,  # sets user_id automatically
                )

        # --- 4) hand off to repository ----------------------------------
        created = await self.operator_repo.create(new_operator)
        return created


    async def create_from_agent(
            self,
            agent_name: str,
            email: str,
            plain_password: str,
            ) -> OperatorModel:
        """
        Build User + Operator for a *console* agent.
        first_name  = agent_name
        last_name   = ""
        """
        # ---------- uniqueness checks ----------------------------------
        if await self.user_repository.get_by_email(email):
            raise AppException(error_key=ErrorKey.EMAIL_ALREADY_EXISTS)

        # ---------- UserModel -----------------------------------------
        console_type = await self.user_types_repository.get_by_name("console")

        new_user = UserModel(
                username=await generate_unique_username(
                        self.user_repository,
                        agent_name,  # first part
                        "",  # no last name
                        ),
                hashed_password=get_password_hash(plain_password),
                email=email,
                is_active=1,
                user_type_id=console_type.id,
                )

        # ---------- OperatorStatistics (all zeros) --------------------
        stats = OperatorStatisticsModel()  # relies on DB defaults

        # ---------- OperatorModel -------------------------------------
        new_operator = OperatorModel(
                first_name=agent_name,
                last_name="ai_agent",
                avatar=None,
                is_active=1,
                operator_statistics=stats,
                user=new_user,
                )

        # ---------- persist & return ----------------------------------
        return await self.operator_repo.add_and_flush(new_operator)

    async def get_all(self) -> list[OperatorModel]:
        return  await self.operator_repo.get_all()

    async def set_operator_latest_call(self, operator: OperatorRead):
        latest_conversation = await self.conversation_repo.get_latest_conversation_with_analysis_for_operator(
                operator.id)
        operator.latest_conversation_analysis = latest_conversation

    async def get_by_id(self, operator_id: UUID) -> OperatorModel:
        # Step 1: Fetch operator with stats
        return  await self.operator_repo.get_by_id(operator_id)

