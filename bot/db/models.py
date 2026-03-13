from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, Numeric,
    Date, Time, DateTime, ForeignKey, SmallInteger, func,
)
from sqlalchemy.orm import relationship

from bot.db.base import Base


class Master(Base):
    __tablename__ = "masters"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String(100))
    about_text = Column(Text)
    photo_file_id = Column(String(200))
    contact_phone = Column(String(20))
    contact_instagram = Column(String(100))
    contact_address = Column(Text)
    timezone = Column(String(50), default="Europe/Minsk")
    is_active = Column(Boolean, default=True)

    categories = relationship("ServiceCategory", back_populates="master", lazy="select")
    schedule_templates = relationship("ScheduleTemplate", back_populates="master", lazy="select")
    schedule_exceptions = relationship("ScheduleException", back_populates="master", lazy="select")
    bookings = relationship("Booking", back_populates="master", lazy="select")
    gallery_photos = relationship("GalleryPhoto", back_populates="master", lazy="select")


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    master = relationship("Master", back_populates="categories")
    services = relationship("Service", back_populates="category", lazy="select")


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("service_categories.id"), nullable=False)
    name = Column(String(200), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    category = relationship("ServiceCategory", back_populates="services")
    booking_services = relationship("BookingService", back_populates="service", lazy="select")


class ScheduleTemplate(Base):
    __tablename__ = "schedule_templates"

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False)
    day_of_week = Column(SmallInteger, nullable=False)  # 0=Mon .. 6=Sun
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    slot_interval_minutes = Column(Integer, default=30)
    is_working = Column(Boolean, default=True)

    master = relationship("Master", back_populates="schedule_templates")


class ScheduleException(Base):
    __tablename__ = "schedule_exceptions"

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False)
    date = Column(Date, nullable=False)
    is_day_off = Column(Boolean, default=False)
    start_time = Column(Time)
    end_time = Column(Time)
    reason = Column(String(200))

    master = relationship("Master", back_populates="schedule_exceptions")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    phone = Column(String(20))
    display_name = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_blocked = Column(Boolean, default=False)

    bookings = relationship("Booking", back_populates="client", lazy="select")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    total_price = Column(Numeric(10, 2))
    total_duration_minutes = Column(Integer)
    status = Column(String(20), default="confirmed")
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reminder_24h_sent = Column(Boolean, default=False)
    reminder_2h_sent = Column(Boolean, default=False)

    client = relationship("Client", back_populates="bookings")
    master = relationship("Master", back_populates="bookings")
    booking_services = relationship(
        "BookingService", back_populates="booking", cascade="all, delete-orphan", lazy="select"
    )


class BookingService(Base):
    __tablename__ = "booking_services"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    price_at_booking = Column(Numeric(10, 2))
    duration_at_booking = Column(Integer)

    booking = relationship("Booking", back_populates="booking_services")
    service = relationship("Service", back_populates="booking_services")


class GalleryPhoto(Base):
    __tablename__ = "gallery_photos"

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False)
    file_id = Column(String(200), nullable=False)
    caption = Column(String(200))
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    master = relationship("Master", back_populates="gallery_photos")
