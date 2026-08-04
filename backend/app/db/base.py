# Import all models to collect metadata for declarative creation
from app.db.database import Base # noqa
from app.models.session import Session # noqa
from app.models.upload import Upload # noqa
from app.models.presentation_job import PresentationJob # noqa
from app.models.presentation import Presentation # noqa
from app.models.presentation_metadata import PresentationMetadata # noqa
from app.models.presentation_script import PresentationScript # noqa
from app.models.presentation_question import PresentationQuestion # noqa
from app.models.employee_list import EmployeeList # noqa
from app.models.organization_config import OrganizationConfig # noqa
from app.models.meeting import Meeting # noqa
from app.models.invitation_draft import InvitationDraft # noqa
from app.models.runtime import Runtime # noqa
from app.models.runtime_message import RuntimeMessage # noqa
from app.models.attendance import Attendance # noqa
from app.models.presentation_asset import PresentationAsset # noqa
from app.models.browser_profile import BrowserProfile # noqa
