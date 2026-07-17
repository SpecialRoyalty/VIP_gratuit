from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GroupRole(str, enum.Enum):
    pending = 'pending'
    pub = 'pub'
    vip = 'vip'
    blocked = 'blocked'


class CampaignStatus(str, enum.Enum):
    awaiting_proof = 'awaiting_proof'
    proof_review = 'proof_review'
    active = 'active'
    vip_active = 'vip_active'
    expired = 'expired'
    cancelled = 'cancelled'
    banned = 'banned'


class ProofStatus(str, enum.Enum):
    pending = 'pending'
    approved = 'approved'
    rejected = 'rejected'


class InviteStatus(str, enum.Enum):
    pending = 'pending'
    valid = 'valid'
    invalid = 'invalid'


class User(Base):
    __tablename__ = 'users'
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Admin(Base):
    __tablename__ = 'admins'
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default='detected')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Group(Base):
    __tablename__ = 'groups'
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    role: Mapped[GroupRole] = mapped_column(Enum(GroupRole), default=GroupRole.pending)
    source_token: Mapped[str] = mapped_column(String(32), unique=True)
    authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    ad_text: Mapped[str | None] = mapped_column(Text)
    ad_photo_file_id: Mapped[str | None] = mapped_column(Text)
    private_photo_file_id: Mapped[str | None] = mapped_column(Text)
    private_intro: Mapped[str | None] = mapped_column(Text)
    vip_group_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('groups.chat_id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Campaign(Base):
    __tablename__ = 'campaigns'
    __table_args__ = (UniqueConstraint('user_id', 'active_slot', name='uq_one_active_campaign'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.telegram_id'), index=True)
    pub_group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('groups.chat_id'))
    vip_group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('groups.chat_id'))
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus), default=CampaignStatus.awaiting_proof)
    active_slot: Mapped[int | None] = mapped_column(Integer, default=1)
    invite_link: Mapped[str] = mapped_column(Text, unique=True)
    phrase_index: Mapped[int] = mapped_column(Integer)
    valid_count: Mapped[int] = mapped_column(Integer, default=0)
    pending_count: Mapped[int] = mapped_column(Integer, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0)
    credited_goals: Mapped[int] = mapped_column(Integer, default=0)
    vip_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vip_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_valid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stagnation_notice_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Proof(Base):
    __tablename__ = 'proofs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey('campaigns.id'), index=True)
    file_id: Mapped[str] = mapped_column(Text)
    status: Mapped[ProofStatus] = mapped_column(Enum(ProofStatus), default=ProofStatus.pending)
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invite(Base):
    __tablename__ = 'invites'
    __table_args__ = (UniqueConstraint('campaign_id', 'joined_user_id', name='uq_campaign_joined_user'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey('campaigns.id'), index=True)
    joined_user_id: Mapped[int] = mapped_column(BigInteger)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    validate_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[InviteStatus] = mapped_column(Enum(InviteStatus), default=InviteStatus.pending)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Reminder(Base):
    __tablename__ = 'reminders'
    __table_args__ = (UniqueConstraint('campaign_id', 'kind', 'reference_date', name='uq_reminder_once'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey('campaigns.id'))
    kind: Mapped[str] = mapped_column(String(32))
    reference_date: Mapped[str] = mapped_column(String(16))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
