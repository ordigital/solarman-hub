"""Validate and stage Companion exports without applying or reconfiguring devices."""
from typing import Literal
from pydantic import Field, model_validator
from .config import Model, Logger
from .profiles import Profile
from .protocol import Frame


class Bundle(Model):
    bundle_version: Literal[1]
    verification: Literal['known-map','unverified']
    profile: Profile
    logger: Logger
    sample_hex: str | None = Field(default=None, max_length=32768)

    @model_validator(mode='after')
    def consistent(self):
        if self.logger.profile != self.profile.id:
            raise ValueError('Bundle logger and profile do not match')
        if self.sample_hex:
            frame=Frame.parse(bytes.fromhex(self.sample_hex))
            if frame.serial!=self.logger.serial or frame.code!=self.profile.match.code or len(frame.raw)!=self.profile.match.length:
                raise ValueError('Bundle sample does not match logger/profile')
        return self


def preview(runtime, bundle):
    profiles=runtime.profiles.load()
    existing=profiles.get(bundle.profile.id)
    conflicts=[]
    if existing and existing.model_dump()!=bundle.profile.model_dump():
        conflicts.append('A different profile already uses this identifier')
    logger=next((item for item in runtime.store.load().loggers if item.serial==bundle.logger.serial),None)
    if logger and logger.profile!=bundle.profile.id:
        conflicts.append('Logger already exists with another profile; import the profile separately or edit the bundle')
    return {'profile':bundle.profile.id,'name':bundle.profile.name,'fields':len(bundle.profile.fields),
            'serial':bundle.logger.serial,'verification':bundle.verification,'contains_sample':bool(bundle.sample_hex),
            'logger_exists':logger is not None,'profile_exists':existing is not None,'conflicts':conflicts,
            'revision':runtime.store.revision(runtime.profiles.documents())}


def install(runtime, bundle):
    status=preview(runtime,bundle)
    if status['conflicts']:
        raise ValueError('; '.join(status['conflicts']))
    config=runtime.store.load()
    created=not status['profile_exists']
    if created:
        runtime.profiles.save(bundle.profile)
    try:
        if not status['logger_exists']:
            config.loggers.append(bundle.logger)
            config=type(config).model_validate(config.model_dump())
            runtime.store.save(config)
    except BaseException:
        if created:
            runtime.profiles.delete(bundle.profile.id)
        raise
    return status
