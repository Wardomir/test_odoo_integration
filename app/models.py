from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from datetime import datetime
from app.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    write_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Contact(odoo_id={self.odoo_id}, name={self.name}, email={self.email})>"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    move_type = Column(String, nullable=False)
    invoice_date = Column(DateTime, nullable=True)
    partner_id = Column(Integer, nullable=True)  # Odoo partner ID
    partner_name = Column(String, nullable=True)  # Partner name from tuple
    amount_total = Column(Float, nullable=True)
    amount_residual = Column(Float, nullable=True)
    state = Column(String, nullable=True)
    currency_id = Column(Integer, nullable=True)  # Odoo currency ID
    currency_name = Column(String, nullable=True)  # Currency name from tuple
    write_date = Column(DateTime, nullable=True)
    create_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Invoice(odoo_id={self.odoo_id}, name={self.name}, amount_total={self.amount_total}, state={self.state})>"
