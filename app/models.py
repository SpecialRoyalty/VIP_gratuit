from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GroupRole(str, enum.Enum):
    pending = 'pending'
    pub = 'pub'
    vip = 'vip'
    blocked = 'blocked'


class CampaignStatus(str, enum.Enum):
    active = 'active'
    suspended = 'suspended'
    banned = 'banned'
    closed = 'closed'


class InviteStatus(str, enum.Enum):
    pending = 'pending'
    valid = 'valid'
    invalid = 'invalid'
    forbidden_profile = 'forbidden_profile'
    duplicate = 'duplicate'


class TrialStatus(str, enum.Enum):
    link_created = 'link_created'
    active = 'active'
    kick_pending = 'kick_pending'
    kicked = 'kicked'
    cancelled = 'cancelled'


class VipSessionStatus(str, enum.Enum):
    link_created = 'link_created'
    active = 'active'
    expired = 'expired'
    kick_pending = 'kick_pending'
    kicked = 'kicked'
    cancelled = 'cancelled'


class EventType(str, enum.Enum):
    ad_published = 'ad_published'
    ad_click = 'ad_click'
    campaign_started = 'campaign_started'
    invite_valid = 'invite_valid'
    invite_invalid = 'invite_invalid'
    vip_link = 'vip_link'
    vip_join = 'vip_join'
    vip_kick = 'vip_kick'
    health_error = 'health_error'
    trial_link = 'trial_link'
    trial_join = 'trial_join'
    trial_kick = 'trial_kick'
    unauthorized_join = 'unauthorized_join'


class User(Base):
    __tablename__ = 'users'
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    forbidden_invites: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Admin(Base):
    __tablename__ = 'admins'
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(32), default='detected')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Group(Base):
    __tablename__ = 'groups'
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[GroupRole] = mapped_column(Enum(GroupRole), default=GroupRole.pending)
    authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    source_token: Mapped[str] = mapped_column(String(48), unique=True)
    vip_group_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('groups.chat_id'))
    ad_text: Mapped[str | None] = mapped_column(Text)
    ad_photo_file_id: Mapped[str | None] = mapped_column(Text)
    ad_version: Mapped[int] = mapped_column(Integer, default=1)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_health_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    health_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Campaign(Base):
    __tablename__ = 'campaigns'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.telegram_id'), index=True)
    pub_group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('groups.chat_id'))
    vip_group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('groups.chat_id'))
    invite_link: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus), default=CampaignStatus.active)
    valid_invites: Mapped[int] = mapped_column(Integer, default=0)
    pending_invites: Mapped[int] = mapped_column(Integer, default=0)
    invalid_invites: Mapped[int] = mapped_column(Integer, default=0)
    minutes_earned: Mapped[int] = mapped_column(Integer, default=0)
    minutes_consumed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Invite(Base):
    __tablename__ = 'invites'
    __table_args__ = (UniqueConstraint('joined_user_id', name='uq_invited_user_global'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey('campaigns.id'), index=True)
    joined_user_id: Mapped[int] = mapped_column(BigInteger)
    joined_username: Mapped[str | None] = mapped_column(String(64))
    joined_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[InviteStatus] = mapped_column(Enum(InviteStatus), default=InviteStatus.pending)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    validate_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(128))


class VipSession(Base):
    __tablename__ = 'vip_sessions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey('campaigns.id'), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    vip_group_id: Mapped[int] = mapped_column(BigInteger)
    invite_link: Mapped[str | None] = mapped_column(Text)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[VipSessionStatus] = mapped_column(Enum(VipSessionStatus), default=VipSessionStatus.link_created)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    allocated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    kick_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_kick_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TrialAccess(Base):
    __tablename__ = 'trial_accesses'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey('campaigns.id'), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    vip_group_id: Mapped[int] = mapped_column(BigInteger)
    invite_link: Mapped[str | None] = mapped_column(Text, unique=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[TrialStatus] = mapped_column(Enum(TrialStatus), default=TrialStatus.link_created)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kick_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_kick_error: Mapped[str | None] = mapped_column(Text)
    kick_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ForbiddenWord(Base):
    __tablename__ = 'forbidden_words'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(128), unique=True)
    exact_word: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MetricEvent(Base):
    __tablename__ = 'metric_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), index=True)
    pub_group_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    ad_version: Mapped[int | None] = mapped_column(Integer)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    value: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class HealthAlert(Base):
    __tablename__ = 'health_alerts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int | None] = mapped_column(BigInteger)
    fingerprint: Mapped[str] = mapped_column(String(255), index=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
