from app.models.enums import Role

# Permission matrix — enforced via FastAPI dependencies, not scattered in routes.


def can_update_tenant(role: Role) -> bool:
    return role == Role.admin


def can_list_members(role: Role) -> bool:
    return role in {Role.admin, Role.manager, Role.individual}


def can_invite_role(inviter_role: Role, invitee_role: Role) -> bool:
    if invitee_role == Role.admin:
        return inviter_role == Role.admin
    if invitee_role in {Role.manager, Role.individual}:
        return inviter_role in {Role.admin, Role.manager}
    return False


def can_manage_invites(role: Role) -> bool:
    return role in {Role.admin, Role.manager}
