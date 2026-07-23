from typing import List, Dict, Any, Optional
from app.modules.induction.employees.excel_parser import parse_employees_excel
from app.modules.induction.employees.profiler import profile_employees
from loguru import logger

class EmployeeContextManager:
    def __init__(self):
        self.employees_list: List[Dict[str, Any]] = []

    def load_employees_from_excel(self, excel_path: str) -> List[Dict[str, Any]]:
        """
        Parses employee records using openpyxl from the given Excel filepath.
        """
        try:
            raw_rows = parse_employees_excel(excel_path)
            self.employees_list = profile_employees(raw_rows)
            logger.info(f"EmployeeContextManager | Loaded {len(self.employees_list)} employee profiles successfully.")
        except Exception as e:
            logger.error(f"EmployeeContextManager | Failed to parse employee file at {excel_path}: {e}")
            self.employees_list = []
        return self.employees_list

    def get_primary_inductee(self) -> Optional[Dict[str, Any]]:
        """
        Fetches the primary employee profile being inducted.
        """
        if self.employees_list:
            return self.employees_list[0]
        return None

    def get_personalized_greeting(self) -> str:
        """
        Generates a personalized structured greeting string.
        """
        inductee = self.get_primary_inductee()
        if not inductee:
            return "Hello and welcome to KONE!"
        
        name = inductee.get("name", "Team Member")
        role = inductee.get("designation", "New Hire")
        dept = inductee.get("department", "General")
        return f"A very warm welcome to {name}, joining us as {role} in the {dept} department!"
