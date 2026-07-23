from app.modules.induction.employees.excel_parser import parse_employees_excel

class EmployeeParser:
    def parse_employees(self, excel_path: str) -> list[dict]:
        """
        Parses and normalizes employee records from Excel.
        """
        return parse_employees_excel(excel_path)

employee_parser = EmployeeParser()
