from types import SimpleNamespace
from uuid import uuid4

from app.repositories.notification import NotificationRepository


def test_user_matches_audience_non_tenant_respects_opt_out():
    nt = SimpleNamespace(is_enabled=True, is_tenant=False, allow_all_tenant_users=True)
    result = NotificationRepository._user_matches_audience(
        nt=nt,
        user_id=uuid4(),
        user_group_id=None,
        supervised_group_ids=[],
        explicit_user_ids=set(),
        explicit_group_ids=set(),
        user_setting_enabled=False,
    )
    assert result is False


def test_user_matches_audience_tenant_allow_all_ignores_user_setting():
    nt = SimpleNamespace(is_enabled=True, is_tenant=True, allow_all_tenant_users=True)
    result = NotificationRepository._user_matches_audience(
        nt=nt,
        user_id=uuid4(),
        user_group_id=None,
        supervised_group_ids=[],
        explicit_user_ids=set(),
        explicit_group_ids=set(),
        user_setting_enabled=False,
    )
    assert result is True


def test_user_matches_audience_group_targeting_for_supervisor():
    group_id = uuid4()
    nt = SimpleNamespace(is_enabled=True, is_tenant=False, allow_all_tenant_users=False)
    result = NotificationRepository._user_matches_audience(
        nt=nt,
        user_id=uuid4(),
        user_group_id=None,
        supervised_group_ids=[group_id],
        explicit_user_ids=set(),
        explicit_group_ids={group_id},
        user_setting_enabled=True,
    )
    assert result is True
