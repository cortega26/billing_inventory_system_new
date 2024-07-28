import xlsxwriter
from datetime import datetime
from typing import List, Dict, Any
import os

class ExcelExporter:
    @staticmethod
    def export_to_excel(data: List[Dict[str, Any]], headers: List[str], filename: str) -> None:
        """
        Export data to an Excel file.

        Args:
            data (List[Dict[str, Any]]): The data to be exported. Each dictionary represents a row.
            headers (List[str]): The column headers for the Excel file.
            filename (str): The name of the file to be created (including path).

        Raises:
            ValueError: If the data is empty or headers don't match the data.
            IOError: If there's an issue writing to the file.
        """
        if not data:
            raise ValueError("No data to export")

        if set(headers) != set(data[0].keys()):
            raise ValueError("Headers don't match the data keys")

        try:
            workbook = xlsxwriter.Workbook(filename)
            worksheet = workbook.add_worksheet()

            # Add headers
            for col, header in enumerate(headers):
                worksheet.write(0, col, header)

            # Add data
            for row, item in enumerate(data, start=1):
                for col, (key, value) in enumerate(item.items()):
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    worksheet.write(row, col, value)

            workbook.close()
            print(f"Excel file created successfully: {os.path.abspath(filename)}")
        except IOError as e:
            raise IOError(f"Error writing to file {filename}: {str(e)}")
        except Exception as e:
            raise Exception(f"An error occurred while exporting to Excel: {str(e)}")