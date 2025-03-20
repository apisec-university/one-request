import jwt
from fastapi import APIRouter
from pydantic import BaseModel

from one_request.ctf.validators import (
    validate_admin_key,
    validate_group,
    validate_activity,
    validate_location,
    validate_user,
    validate_invite_code,
)
from one_request.exceptions import ValidationError

router = APIRouter(tags=["One Request"])


class FlagValidateIn(BaseModel):
    flag: str


@router.post("/submit/one-request")
async def validate_one_request(body: FlagValidateIn) -> bool:
    return body.flag == "onerequest{osgiliath_passages_protect_us}"


@router.post("/submit/shadow-artisans-mark")
async def validate_shadow_artisan(body: FlagValidateIn) -> bool:
    try:
        validate_user(body.flag)
        return True
    except ValidationError:
        return False


@router.post("/submit/forge-masters-circle")
async def validate_forge_master(body: FlagValidateIn) -> bool:
    try:
        validate_group(body.flag)
        return True
    except ValidationError:
        return False


@router.post("/submit/whispers-in-the-dark")
async def validate_whispers(body: FlagValidateIn) -> bool:
    try:
        validate_activity(body.flag)
        return True
    except ValidationError:
        return False


@router.post("/submit/forging-the-seeing-stones-key")
async def validate_seeing_stone(body: FlagValidateIn) -> bool:
    try:
        await validate_admin_key(body.flag)
        return True
    except ValidationError:
        return False
    except jwt.PyJWTError:
        return False



@router.post("/submit/traps-staging-ground")
async def validate_trap_staging(body: FlagValidateIn) -> bool:
    try:
        validate_location(body.flag)
        return True
    except ValidationError:
        return False

@router.post("/submit/key-of-passage")
async def validate_key_passage(body: FlagValidateIn) -> bool:
    try:
        validate_invite_code(body.flag)
        return True
    except ValidationError:
        return False
