# --- START OF traffic_app/models.py ---
import enum
from datetime import datetime
from sqlalchemy import Enum as SQLAlchemyEnum # Alias to avoid conflict if we use our own Enum
from .extensions import db # Import db from extensions
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List # Make sure Optional and List are imported

# --- Database Models ---
class ProcessingStatus(enum.Enum):
    PENDING_CONFIG = "PENDING_CONFIG"
    PENDING_FILES = "PENDING_FILES"
    READY_TO_PROCESS = "READY_TO_PROCESS"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"

class Study(db.Model):
    __tablename__ = 'study'
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False, unique=True)
    analyst_name: Mapped[Optional[str]] = mapped_column(db.String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, nullable=False)

    configurations: Mapped[List["Configuration"]] = relationship(
        back_populates="study", cascade="all, delete-orphan", lazy="select"
    )
    # Relationship to Scenario, assuming Scenario.study will use back_populates="scenarios"
    scenarios: Mapped[List["Scenario"]] = relationship(
        back_populates="study", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self):
        return f"<Study {self.id}: {self.name}>"

class Configuration(db.Model):
    __tablename__ = 'configuration'
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    phases_n: Mapped[int] = mapped_column(db.Integer, default=0)
    include_bg_dist: Mapped[bool] = mapped_column(db.Boolean, default=False)
    include_bg_assign: Mapped[bool] = mapped_column(db.Boolean, default=False)
    include_trip_dist: Mapped[bool] = mapped_column(db.Boolean, default=False)
    trip_dist_count: Mapped[int] = mapped_column(db.Integer, default=1)
    include_trip_assign: Mapped[bool] = mapped_column(db.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, nullable=False)
    study_id: Mapped[int] = mapped_column(db.ForeignKey('study.id'), nullable=False)

    study: Mapped["Study"] = relationship(back_populates="configurations")
    scenarios: Mapped[List["Scenario"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self):
        return f"<Configuration {self.id}: {self.name} (Study {self.study_id})>"

class Scenario(db.Model):
    __tablename__ = 'scenario'
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    # Ensure ForeignKey constraints are correctly pointing to tablename.columnname
    study_id: Mapped[int] = mapped_column(db.ForeignKey('study.id'), nullable=False)
    configuration_id: Mapped[int] = mapped_column(db.ForeignKey('configuration.id'), nullable=False) 
    status: Mapped[ProcessingStatus] = mapped_column(SQLAlchemyEnum(ProcessingStatus), default=ProcessingStatus.PENDING_CONFIG, nullable=False)
    status_message: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    am_csv_path: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)
    pm_csv_path: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)
    attout_txt_path: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)

    # --- Add these new fields for original filenames ---
    am_csv_original_name: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)
    pm_csv_original_name: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)
    attout_txt_original_name: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)
    # --- End of new fields ---

    merged_csv_path: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)
    attin_txt_path: Mapped[Optional[str]] = mapped_column(db.String(255), nullable=True)

    study: Mapped["Study"] = relationship(back_populates="scenarios")
    configuration: Mapped["Configuration"] = relationship(back_populates="scenarios")

    def __repr__(self):
        return f"<Scenario {self.id}: {self.name} (Study {self.study_id}, Config {self.configuration_id})>"

    def has_file(self, file_type):
        """Check if a specific file type exists for this scenario.

        Args:
            file_type (str): One of 'am_csv', 'pm_csv', 'attout', 'merged', 'attin'

        Returns:
            bool: True if the file exists, False otherwise
        """
        attr_map = {
            'am_csv': 'am_csv_path',
            'pm_csv': 'pm_csv_path',
            'attout': 'attout_txt_path',
            'merged': 'merged_csv_path',
            'attin': 'attin_txt_path'
        }
        attr_name = attr_map.get(file_type)
        if not attr_name:
            raise ValueError(f"Invalid file type: {file_type}")
        return bool(getattr(self, attr_name))

    # Keep these properties for backward compatibility
    @property
    def has_am_csv(self):
        return self.has_file('am_csv')

    @property
    def has_pm_csv(self):
        return self.has_file('pm_csv')

    @property
    def has_attout(self):
        return self.has_file('attout')

    @property
    def has_merged(self):
        return self.has_file('merged')

    @property
    def has_attin(self):
        return self.has_file('attin')

# --- END OF traffic_app/models.py ---