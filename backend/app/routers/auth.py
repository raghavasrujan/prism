"""Auth routes: register / login / refresh / logout / me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models_db.user import User
from app.repositories import provider_models as pm_repo
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UpdateMeRequest,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_context(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return ua, ip


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenPair:
    ua, ip = _client_context(request)
    user, access, refresh, exp = auth_service.register(
        db,
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        user_agent=ua,
        ip=ip,
    )
    return TokenPair(
        access=access,
        refresh=refresh,
        access_expires_at=exp,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenPair)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenPair:
    ua, ip = _client_context(request)
    user, access, refresh, exp = auth_service.login(
        db, email=body.email, password=body.password, user_agent=ua, ip=ip
    )
    return TokenPair(
        access=access, refresh=refresh, access_expires_at=exp, user=UserOut.model_validate(user)
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(
    body: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenPair:
    ua, ip = _client_context(request)
    user, access, refresh_new, exp = auth_service.refresh(
        db, raw_token=body.refresh, user_agent=ua, ip=ip
    )
    return TokenPair(
        access=access,
        refresh=refresh_new,
        access_expires_at=exp,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutRequest, db: Session = Depends(get_db)) -> None:
    auth_service.logout(db, raw_token=body.refresh)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_me(
    body: UpdateMeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """Update the current user's mutable profile fields.

    Fields set to ``None`` in the request payload are left unchanged; sending
    an empty string / null explicitly clears the field where allowed.
    """
    data = body.model_dump(exclude_unset=True)

    if "display_name" in data:
        user.display_name = data["display_name"]

    if "title_provider_model_id" in data:
        model_id = data["title_provider_model_id"]
        if model_id:
            # Validate the model belongs to this user so we don't let people
            # reference someone else's key material by id.
            if pm_repo.get_for_user(db, user.id, model_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unknown provider model",
                )
            user.title_provider_model_id = model_id
        else:
            user.title_provider_model_id = None

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
